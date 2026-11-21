"""Orchestrator: discovery -> dedup -> screening -> store -> digest."""
import argparse
import pathlib
from datetime import datetime, timedelta, timezone
import yaml

from . import db, sources
from .screening import screen

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(name):
    p = ROOT / "config" / name
    return yaml.safe_load(p.read_text()) if p.exists() else {}


TARGET_TOTAL, TARGET_STRONG, STRONG_SCORE = 40, 20, 80


def run(jobs=None, db_path=None, log=print, max_age_hours=3):
    profile, roles, companies = load("profile.yaml"), load("roles.yaml"), load("companies.yaml")
    con = db.connect(db_path or str(ROOT / "jobs.db"))
    if jobs is None:
        jobs = sources.discover(roles, companies, log)
    kept = dup = dropped = stale = 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours) if max_age_hours else None
    run_rows = []
    for j in jobs:
        d = j.posted_dt
        if cutoff and d is not None and d < cutoff:
            stale += 1
            continue
        if db.seen(con, j):
            dup += 1
            continue
        if screen(j, roles["roles"], profile):
            j.status = "new"; db.save(con, j); kept += 1; run_rows.append(j)
        else:
            dropped += 1
    strong = sum(1 for j in run_rows if j.score >= STRONG_SCORE)
    log(f"[pipeline] {len(jobs)} fetched, {stale} older than {max_age_hours}h, {dup} duplicates, "
        f"{dropped} screened out, {kept} new matches")
    log(f"[target] total {kept}/{TARGET_TOTAL} {'OK' if kept >= TARGET_TOTAL else 'SHORT'} | "
        f"{STRONG_SCORE}+ score {strong}/{TARGET_STRONG} {'OK' if strong >= TARGET_STRONG else 'SHORT'}")
    if kept < TARGET_TOTAL or strong < TARGET_STRONG:
        log("[target] shortfall: add companies to config/companies.yaml or enable a job-search API source")
    return con


def digest(con, limit=20):
    lines = ["# Job digest", ""]
    for r in db.top(con, "new", limit):
        tag = "REMOTE" if r["remote"] else r["location"]
        lines.append(f"- **{r['score']:.0f}** | {r['role']} | {r['title']} @ {r['company']} "
                     f"| {r['employment_type']} | {tag}\n  {r['url']}\n  _{'; '.join(__import__('json').loads(r['reasons']))}_")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["run", "digest", "mark"])
    ap.add_argument("--key"); ap.add_argument("--status")
    ap.add_argument("--hours", type=float, default=3, help="only postings newer than this (0 = no limit)")
    a = ap.parse_args()
    con = db.connect(str(ROOT / "jobs.db"))
    if a.command == "run":
        con = run(max_age_hours=a.hours); print(digest(con))
    elif a.command == "digest":
        print(digest(con))
    else:
        db.set_status(con, a.key, a.status); print("ok")


if __name__ == "__main__":
    main()
