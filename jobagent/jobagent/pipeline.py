"""Orchestrator: discovery -> dedup -> screening -> store -> digest."""
import argparse
import pathlib
import yaml

from . import db, sources
from .screening import screen

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(name):
    p = ROOT / "config" / name
    return yaml.safe_load(p.read_text()) if p.exists() else {}


def run(jobs=None, db_path=None, log=print):
    profile, roles, companies = load("profile.yaml"), load("roles.yaml"), load("companies.yaml")
    con = db.connect(db_path or str(ROOT / "jobs.db"))
    if jobs is None:
        jobs = sources.discover(roles, companies, log)
    kept = dup = dropped = 0
    for j in jobs:
        if db.seen(con, j):
            dup += 1
            continue
        if screen(j, roles["roles"], profile):
            j.status = "new"; db.save(con, j); kept += 1
        else:
            dropped += 1
    log(f"[pipeline] {len(jobs)} fetched, {dup} duplicates, {dropped} screened out, {kept} new matches")
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
    a = ap.parse_args()
    con = db.connect(str(ROOT / "jobs.db"))
    if a.command == "run":
        con = run(); print(digest(con))
    elif a.command == "digest":
        print(digest(con))
    else:
        db.set_status(con, a.key, a.status); print("ok")


if __name__ == "__main__":
    main()
