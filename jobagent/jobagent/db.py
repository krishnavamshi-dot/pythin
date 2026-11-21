import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  key TEXT PRIMARY KEY, source TEXT, title TEXT, company TEXT, location TEXT,
  url TEXT, remote INTEGER, posted TEXT, employment_type TEXT,
  role TEXT, score REAL, reasons TEXT, status TEXT DEFAULT 'new',
  resume TEXT, notes TEXT, first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
  dedup TEXT
);
CREATE INDEX IF NOT EXISTS idx_dedup ON jobs(dedup);
"""

STATUSES = ["new", "shortlisted", "applied", "screen", "interview", "offer", "rejected", "skipped"]


def connect(path="jobs.db"):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def dedup_key(job):
    norm = lambda s: "".join(c for c in s.lower() if c.isalnum())
    return f"{norm(job.company)}|{norm(job.title)}"


def seen(con, job):
    r = con.execute("SELECT 1 FROM jobs WHERE key=? OR dedup=?", (job.key, dedup_key(job))).fetchone()
    return r is not None


def save(con, job):
    con.execute(
        "INSERT OR IGNORE INTO jobs (key,source,title,company,location,url,remote,posted,"
        "employment_type,role,score,reasons,status,dedup) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (job.key, job.source, job.title, job.company, job.location, job.url, int(job.remote),
         job.posted, job.employment_type, job.role, job.score, json.dumps(job.reasons),
         job.status, dedup_key(job)),
    )
    con.commit()


def set_status(con, key, status, notes=None):
    assert status in STATUSES, f"status must be one of {STATUSES}"
    con.execute("UPDATE jobs SET status=?, notes=COALESCE(?,notes) WHERE key=?", (status, notes, key))
    con.commit()


def top(con, status="new", limit=25):
    return con.execute(
        "SELECT * FROM jobs WHERE status=? ORDER BY score DESC LIMIT ?", (status, limit)
    ).fetchall()
