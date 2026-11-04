"""Tiny capture databases built in-test from SQL (architecture §12). Tester-owned.

The DDL is the capture schema exactly as `ux-extension/server/src/db.ts` creates it (frozen,
architecture §3.1), copied from `data/reference/capture.db`. `with_analyzer=False` builds the
same file without the old analyzer's `attempts*` tables and `sessions.analysis_*` columns, so
a test can prove the loader never needs them.

Rows are given as plain dicts so each test states exactly what it puts in.
"""

import json
import sqlite3
from pathlib import Path

SENTINEL = "SENTINEL_ANALYZER_OUTPUT_7f3a"  # planted in analyzer-only data; must never be loaded

_SESSIONS = """
CREATE TABLE sessions (
  id               TEXT PRIMARY KEY,
  slug             TEXT NOT NULL,
  started_at       TEXT NOT NULL,
  last_activity_at TEXT NOT NULL,
  ended_at         TEXT,
  end_reason       TEXT{analysis}
);
CREATE INDEX sessions_slug ON sessions(slug, ended_at);
"""
_ANALYSIS_COLS = """,
  analysis_status  TEXT NOT NULL DEFAULT 'open',
  analysis_error   TEXT"""

_REST = """
CREATE TABLE snapshots (
  id         INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  ts         TEXT NOT NULL,
  language   TEXT,
  code       TEXT NOT NULL,
  partial    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX snapshots_session ON snapshots(session_id, ts);
CREATE TABLE judge_events (
  id           INTEGER PRIMARY KEY,
  session_id   TEXT NOT NULL REFERENCES sessions(id),
  ts           TEXT NOT NULL,
  kind         TEXT NOT NULL,
  status       TEXT NOT NULL,
  tests_passed INTEGER,
  tests_total  INTEGER,
  runtime      TEXT,
  memory       TEXT,
  error_detail TEXT,
  language     TEXT,
  submission_id TEXT
);
CREATE INDEX judge_session ON judge_events(session_id, ts);
CREATE UNIQUE INDEX judge_submission ON judge_events(session_id, submission_id);
CREATE TABLE problems (
  slug         TEXT PRIMARY KEY,
  frontend_id  TEXT,
  title        TEXT NOT NULL,
  difficulty   TEXT,
  tags         TEXT NOT NULL DEFAULT '[]',
  category     TEXT,
  description  TEXT,
  paid_only    INTEGER NOT NULL DEFAULT 0,
  ac_rate      REAL,
  updated_at   TEXT NOT NULL
);
"""
_ANALYZER_TABLES = """
CREATE TABLE attempts (
  id INTEGER PRIMARY KEY, session_id TEXT, slug TEXT, date TEXT, status TEXT,
  category TEXT, created_at TEXT, verdict_reason TEXT
);
CREATE TABLE attempt_gaps (id INTEGER PRIMARY KEY, attempt_id INTEGER, gap TEXT);
"""

PROBLEM = {
    "slug": "probe-problem", "title": "Probe Problem", "difficulty": "Medium",
    "tags": ["array", "hash-table"], "description": "Given nums, return something.",
}


def build(path: Path, *, sessions: list[dict], snapshots: list[dict] = (), judge_events: list[dict] = (),
          problems: list[dict] = (PROBLEM,), with_analyzer: bool = True) -> Path:
    """Write a capture DB at `path`. Missing optional columns get capture-like defaults."""
    con = sqlite3.connect(path)
    con.executescript(_SESSIONS.format(analysis=_ANALYSIS_COLS if with_analyzer else "") + _REST
                      + (_ANALYZER_TABLES if with_analyzer else ""))
    for p in problems:
        con.execute(
            "INSERT INTO problems (slug, title, difficulty, tags, description, updated_at) VALUES (?,?,?,?,?,?)",
            (p["slug"], p["title"], p["difficulty"], json.dumps(p["tags"]), p.get("description"),
             "2026-11-01T00:00:00.000Z"),
        )
    for s in sessions:
        cols = {"id": s["id"], "slug": s.get("slug", PROBLEM["slug"]), "started_at": s["started_at"],
                "last_activity_at": s.get("last_activity_at", s["started_at"]),
                "ended_at": s.get("ended_at"), "end_reason": s.get("end_reason", "ended")}
        if with_analyzer:
            cols |= {"analysis_status": "done", "analysis_error": SENTINEL}
        con.execute(f"INSERT INTO sessions ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    tuple(cols.values()))
        if with_analyzer:
            con.execute("INSERT INTO attempts (session_id, slug, date, status, category, created_at, verdict_reason)"
                        " VALUES (?,?,?,?,?,?,?)",
                        (s["id"], cols["slug"], "2026-11-01", "failed", SENTINEL, "now", SENTINEL))
            con.execute("INSERT INTO attempt_gaps (attempt_id, gap) VALUES (last_insert_rowid(), ?)", (SENTINEL,))
    for n in snapshots:
        con.execute("INSERT INTO snapshots (id, session_id, ts, language, code) VALUES (?,?,?,?,?)",
                    (n.get("id"), n["session_id"], n["ts"], n.get("language", "python3"), n["code"]))
    for j in judge_events:
        con.execute(
            "INSERT INTO judge_events (id, session_id, ts, kind, status, tests_passed, tests_total, error_detail,"
            " language, submission_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (j.get("id"), j["session_id"], j["ts"], j["kind"], j["status"], j.get("tests_passed"),
             j.get("tests_total"), j.get("error_detail"), "python3", j.get("submission_id")),
        )
    con.commit()
    con.close()
    return path


VERDICT_HEADER = "n,session_id,slug,attempt,minutes,last_run,verdict,tests_passed,tests_total,note\n"


def write_verdicts(path: Path, rows: list[dict]) -> Path:
    """Write a verdicts.csv in the human's format (D-005). Each row: session_id, verdict, passed, total, note."""
    lines = [VERDICT_HEADER]
    for i, r in enumerate(rows, 1):
        lines.append(",".join([
            str(i), r["session_id"], r.get("slug", PROBLEM["slug"]), "1", "5.0", "Passed sample tests",
            r.get("verdict", ""), str(r.get("passed", "")), str(r.get("total", "")),
            f'"{r["note"]}"' if r.get("note") else "",
        ]) + "\n")
    path.write_text("".join(lines))
    return path
