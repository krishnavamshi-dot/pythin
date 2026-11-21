"""Screening: rule-based, explainable fit scoring. Swap `score_job` for an LLM call later."""
import re

US_HINTS = ("usa", "united states", "u.s.", "us only", "north america", "americas", "anywhere", "worldwide")
JUNIOR = re.compile(r"\b(entry[- ]level|junior|jr\.?|associate|new grad|graduate|0-2|0 to 2|1-2|early career)\b", re.I)
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|director|head of|vp|architect|[5-9]\+? years|10\+ years)\b", re.I)


def _contains(text, phrase):
    return re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", text) is not None


def _location_ok(job, prefs):
    loc = job.location.lower()
    if not loc or job.remote:
        # remote jobs restricted to non-US regions are out
        return not re.search(r"\b(europe|emea|apac|asia|uk|india|canada only|latam|germany|france)\b", loc) \
            or any(h in loc for h in US_HINTS)
    return any(h in loc for h in US_HINTS) or bool(re.search(r",\s*[A-Z]{2}\b", job.location))


def score_job(job, role, profile):
    """Return (score 0-100, reasons) or (None, [reject reason])."""
    text = f"{job.title} {job.description}".lower()
    title = job.title.lower()
    auth = profile["authorization_rules"]
    prefs = profile["preferences"]

    for p in auth["reject_phrases"]:
        if p in text:
            return None, [f"rejected: '{p}'"]
    if not _location_ok(job, prefs):
        return None, ["rejected: location outside USA"]

    reasons, score = [], 0.0
    if any(t in title for t in role["titles"]):
        score += 35; reasons.append("title match")
    elif any(t.split()[0] in title for t in role["titles"]):
        score += 10; reasons.append("partial title match")
    else:
        return None, ["no title match"]

    must = [s for s in role["must_have"] if _contains(text, s)]
    if role["must_have"]:
        frac = len(must) / len(role["must_have"])
        score += 20 * frac
        if frac < 1:
            reasons.append(f"missing must-have: {sorted(set(role['must_have']) - set(must))}")
    else:
        score += 10
    nice = [s for s in role["nice_to_have"] if _contains(text, s)]
    score += min(20, 4 * len(nice))
    if nice:
        reasons.append(f"skills: {nice[:6]}")

    mine = [s for s in profile["candidate"]["skills"] if _contains(text, s)]
    score += min(5, len(mine))

    if SENIOR.search(job.title):
        return None, ["rejected: senior-level title"]
    if SENIOR.search(text[:400]) and not JUNIOR.search(text):
        score -= 25; reasons.append("senior-level signals in description")
    elif JUNIOR.search(text):
        score += 10; reasons.append("entry-level friendly")

    if job.remote:
        score += 8 if prefs["remote_preference"] == "strong" else 3
        reasons.append("remote")

    boosts = [p for p in auth["boost_phrases"] if _contains(text, p)]
    if boosts:
        score += 10; reasons.append(f"authorization-friendly: {boosts}")

    score *= prefs["employment_types"].get(job.employment_type, 0.5) ** 0.5  # full-time first, CPT second
    if role["tier"] == "primary":
        score += 5
    return round(max(0, min(100, score)), 1), reasons


def screen(job, roles, profile):
    """Score against all roles; keep the best. Returns True if the job should be kept."""
    best = None
    for role in roles:
        s, why = score_job(job, role, profile)
        if s is None:
            if best is None:
                job.reasons = why
            continue
        if best is None or s > best[0]:
            best = (s, role, why)
    if best is None:
        return False
    job.score, job.role, job.reasons = best[0], best[1]["name"], best[2]
    prefs = profile["preferences"]
    bar = prefs["min_score"] if best[1]["tier"] == "primary" else prefs["secondary_min_score"]
    return job.score >= bar
