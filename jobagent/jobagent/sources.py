"""Discovery: one small subagent-style function per source.

Only official/public feeds are used (no scraping of sites that forbid it).
Each fetcher returns list[Job] and never raises: a failing source is logged and skipped.
"""
import re
import requests

from .models import Job

TIMEOUT = 20
UA = {"User-Agent": "job-search-agent/0.1"}


def _strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def _etype(title, desc):
    text = f"{title} {desc[:600]}".lower()
    if re.search(r"\b(cpt|intern(ship)?|co-?op)\b", text):
        return "cpt"
    return "full_time"


def remotive(queries):
    out = []
    for q in queries:
        r = requests.get("https://remotive.com/api/remote-jobs", params={"search": q, "limit": 50},
                         headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            desc = _strip(j.get("description"))
            out.append(Job("remotive", str(j["id"]), j["title"], j["company_name"],
                           j.get("candidate_required_location", "Remote"), j["url"], desc,
                           True, j.get("publication_date", ""), _etype(j["title"], desc)))
    return out


def arbeitnow(queries):
    r = requests.get("https://www.arbeitnow.com/api/job-board-api", headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for j in r.json().get("data", []):
        desc = _strip(j.get("description"))
        out.append(Job("arbeitnow", j["slug"], j["title"], j["company_name"], j.get("location", ""),
                       j["url"], desc, bool(j.get("remote")), str(j.get("created_at", "")),
                       _etype(j["title"], desc)))
    return out


def greenhouse(boards):
    """Public Greenhouse job-board API for companies you pick (edit config/companies.yaml)."""
    out = []
    for b in boards:
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{b}/jobs",
                         params={"content": "true"}, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            desc = _strip(j.get("content"))
            loc = (j.get("location") or {}).get("name", "")
            out.append(Job(f"greenhouse:{b}", str(j["id"]), j["title"], b, loc, j["absolute_url"],
                           desc, "remote" in loc.lower(), j.get("updated_at", ""),
                           _etype(j["title"], desc)))
    return out


def lever(boards):
    out = []
    for b in boards:
        r = requests.get(f"https://api.lever.co/v0/postings/{b}", params={"mode": "json"},
                         headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        for j in r.json():
            desc = j.get("descriptionPlain", "")
            loc = (j.get("categories") or {}).get("location", "")
            out.append(Job(f"lever:{b}", j["id"], j["text"], b, loc, j["hostedUrl"], desc,
                           "remote" in loc.lower(), str(j.get("createdAt", "")),
                           _etype(j["text"], desc)))
    return out


def discover(role_cfg, company_cfg, log=print):
    queries = sorted({t for r in role_cfg["roles"] for t in r["titles"]})
    jobs = []
    plan = [("remotive", lambda: remotive(queries)), ("arbeitnow", lambda: arbeitnow(queries))]
    if os.environ.get("APIFY_TOKEN"):
        plan.append(("linkedin", lambda: linkedin(queries)))
    if company_cfg.get("greenhouse"):
        plan.append(("greenhouse", lambda: greenhouse(company_cfg["greenhouse"])))
    if company_cfg.get("lever"):
        plan.append(("lever", lambda: lever(company_cfg["lever"])))
    for name, fn in plan:
        try:
            got = fn()
            log(f"[discovery] {name}: {len(got)} postings")
            jobs += got
        except Exception as e:  # one failing source must not stop the run
            log(f"[discovery] {name} FAILED: {type(e).__name__}: {e}")
    return jobs


# ---- LinkedIn via the Apify actor curious_coder/linkedin-jobs-scraper -------------------------
import os
from datetime import datetime, timedelta, timezone

_REL = re.compile(r"(\d+)\s*(minute|hour|day|week|month)s?\s+ago", re.I)
_UNIT = {"minute": 1 / 60, "hour": 1, "day": 24, "week": 168, "month": 720}


def relative_to_dt(text, now=None):
    """'27 minutes ago' -> aware datetime. Returns None if unparseable."""
    m = _REL.search(text or "")
    if not m:
        return None
    now = now or datetime.now(timezone.utc)
    return now - timedelta(hours=int(m.group(1)) * _UNIT[m.group(2).lower()])


def linkedin_items_to_jobs(items, now=None):
    out = []
    for it in items:
        if it.get("error") or not it.get("id"):
            continue
        desc = it.get("descriptionText") or ""
        title = it.get("title", "")
        et = _etype(title, desc)
        if (it.get("employmentType") or "").lower().startswith("intern"):
            et = "cpt"
        loc = it.get("location", "")
        dt = relative_to_dt(it.get("postedAtRelative"), now)
        posted = dt.isoformat() if dt else (it.get("postedAt") or "")
        remote = bool(re.search(r"\bremote\b", f"{title} {loc}", re.I))
        out.append(Job("linkedin", str(it["id"]), title, it.get("companyName", ""), loc,
                       (it.get("link") or "").split("?")[0], desc, remote, posted, et))
    return out


def linkedin(queries, location="United States", per_query=50, token=None):
    """Runs the Apify actor through the REST API (needs APIFY_TOKEN and api.apify.com reachable)."""
    token = token or os.environ.get("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN not set")
    items = []
    for q in queries:
        r = requests.post(
            "https://api.apify.com/v2/acts/curious_coder~linkedin-jobs-scraper/run-sync-get-dataset-items",
            params={"token": token},
            json={"keywords": q, "location": location, "datePosted": "past24Hours",
                  "limitPerSource": per_query, "scrapeCompany": False},
            timeout=300)
        r.raise_for_status()
        items += r.json()
    return linkedin_items_to_jobs(items)
