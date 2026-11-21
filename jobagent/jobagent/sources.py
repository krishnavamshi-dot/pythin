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
