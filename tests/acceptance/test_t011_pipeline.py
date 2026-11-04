"""Acceptance tests for T-011: the deterministic pipeline (architecture §5.6, §13; D-012).

Tester-owned (`/test write T-011`, 2026-11-03). Interfaces (D-037, human approved):

    tutor analyze [--since YYYY-MM-DD]   # live capture (paths.capture_db, mode=ro) → analysis.db, one transaction
    tutor rebuild-timelines              # re-condense every loadable session, one transaction
    tutor check                          # exit 1 if any session_analysis row's condenser_version ≠ its timeline's
    Exit 0 on success, 1 on error (D-030). `--since` is a date in time.timezone: sessions that
    started on or after its local midnight.
    pipeline.jsonl events: session_loaded, session_condensed, session_excluded (the loader's, with
    `reason`), timeline_orphaned. Each line has session_id and run_id; one command run = one run_id.
    The condenser takes interval_s / error_max_chars / token_budget from settings.condenser.

Every test runs the CLI in-process on a tiny capture DB built here, never on data/.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta

import pytest

from _capture_fixture import PROBLEM, build

BIG = "\n".join(f"line_{i:03d} = compute(nums, {i})  # " + "z" * 20 for i in range(100))   # ≈ 5,000 chars


def ts(base: str, minutes: float) -> str:
    t = datetime.fromisoformat(base.replace("Z", "+00:00")) + timedelta(minutes=minutes)
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


A, B, C, D = "s-pass", "s-runs", "s-idle", "s-later"
A0 = "2026-11-01T14:00:00.000Z"   # 09:00 EST Nov 1
B0 = "2026-11-01T20:00:00.000Z"   # 15:00 EST Nov 1
C0 = "2026-11-01T21:00:00.000Z"
D0 = "2026-11-03T02:00:00.000Z"   # 21:00 EST Nov 2 → local date 2026-11-02

SESSIONS = [{"id": A, "started_at": A0}, {"id": B, "started_at": B0}, {"id": C, "started_at": C0},
            {"id": D, "started_at": D0}]
SNAPSHOTS = ([{"session_id": A, "ts": ts(A0, m), "code": f"a = {m}"} for m in (0, 3, 6)]
             + [{"session_id": B, "ts": ts(B0, m), "code": f"b = {m}"} for m in (0, 2, 5)]
             + [{"session_id": C, "ts": C0, "code": "stub"}]
             + [{"session_id": D, "ts": ts(D0, 0), "code": BIG}, {"session_id": D, "ts": ts(D0, 1), "code": BIG + "\n# v2"}])
JUDGE = [
    {"session_id": A, "ts": ts(A0, 4), "kind": "run", "status": "Wrong Answer (sample tests)", "tests_passed": 0,
     "tests_total": 2, "submission_id": "runcode_1"},
    {"session_id": A, "ts": ts(A0, 7.5), "kind": "submit", "status": "Accepted", "tests_passed": 5,
     "tests_total": 5, "submission_id": "100"},
    {"session_id": B, "ts": ts(B0, 3), "kind": "run", "status": "Runtime Error", "submission_id": "runcode_2"},
    {"session_id": B, "ts": ts(B0, 6), "kind": "run", "status": "Passed sample tests", "tests_passed": 2,
     "tests_total": 2, "submission_id": "runcode_3"},
    {"session_id": D, "ts": ts(D0, 2), "kind": "submit", "status": "Wrong Answer", "tests_passed": 3,
     "tests_total": 9, "submission_id": "200"},
]

# Hand-worked expectations (sessions table).
EXPECTED = {
    # session: (attempted_at_utc, local date, time_to_finish, status, source, verdict, passed, total, runs, submits)
    A: (A0, "2026-11-01", 7.5, "passed", "capture_submit", "Accepted", 5, 5, 1, 1),
    # before the 2026-11-04 cutoff and no submit → unknown / not_captured; ends at the last run (6:00)
    B: (B0, "2026-11-01", 6.0, "unknown", "not_captured", None, None, None, 2, 0),
    D: (D0, "2026-11-02", 2.0, "failed_wrong_answer", "capture_submit", "Wrong Answer", 3, 9, 0, 1),
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    capture = build(tmp_path / "capture.db", sessions=SESSIONS, snapshots=SNAPSHOTS, judge_events=JUDGE)
    monkeypatch.setenv("TUTOR__PATHS__CAPTURE_DB", str(capture))
    monkeypatch.setenv("TUTOR__PATHS__EVAL_CAPTURE_DB", str(tmp_path / "frozen-not-used.db"))
    monkeypatch.setenv("TUTOR__PATHS__ANALYSIS_DB", str(tmp_path / "analysis.db"))
    monkeypatch.setenv("TUTOR__PATHS__VERDICTS", str(tmp_path / "no-verdicts.csv"))
    monkeypatch.setenv("TUTOR__PATHS__LOGS", str(tmp_path / "logs"))
    return tmp_path


def tutor(*args):
    from tutor.cli import main

    return main(list(args))


@pytest.fixture
def migrated(env):
    assert tutor("migrate") == 0
    return env


@pytest.fixture
def analyzed(migrated):
    assert tutor("analyze") == 0
    return migrated


def q(tmp_path, sql, *params):
    con = sqlite3.connect(tmp_path / "analysis.db")
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, params)]
    finally:
        con.close()


def log(tmp_path):
    path = tmp_path / "logs" / "pipeline.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


# ---------------------------------------------------------------- Done-when 1: what analyze writes


def test_dw1_sessions_rows_hold_the_hand_worked_facts(analyzed):
    rows = {r["session_id"]: r for r in q(analyzed, "SELECT * FROM sessions")}
    assert set(rows) == {A, B, D}, "the excluded session is not stored"
    for sid, (utc, local, ttf, status, source, verdict, passed, total, runs, submits) in EXPECTED.items():
        r = rows[sid]
        assert _utc(r["attempted_at_utc"]) == _utc(utc), sid
        assert _utc(r["attempted_at_utc"]).utcoffset() == timedelta(0), "stored as UTC"
        assert (r["attempted_date_local"], r["time_to_finish_min"], r["status"], r["status_source"]) == \
            (local, ttf, status, source), sid
        assert (r["leetcode_verdict"], r["tests_passed"], r["tests_total"]) == (verdict, passed, total), sid
        assert (r["run_count"], r["submit_count"], r["slug"]) == (runs, submits, PROBLEM["slug"]), sid
        assert r["loaded_at"]


def test_dw1_problems_row(analyzed):
    [p] = q(analyzed, "SELECT * FROM problems")
    assert (p["slug"], p["title"], p["difficulty"], json.loads(p["tags"])) == \
        (PROBLEM["slug"], PROBLEM["title"], PROBLEM["difficulty"], PROBLEM["tags"])


def test_dw1_timelines_are_stored_and_rerender_exactly(analyzed):
    from tutor.condense import render
    from tutor.models import CondensedSession

    rows = {r["session_id"]: r for r in q(analyzed, "SELECT * FROM condensed_timelines")}
    assert set(rows) == {A, B, D}
    for sid, r in rows.items():
        c = CondensedSession.model_validate_json(r["timeline_json"])
        assert c.session_id == sid and r["condenser_version"] == c.condenser_version == "c1"
        assert render(c) == r["rendered_text"], "the stored JSON regenerates the stored text"
        assert r["est_tokens"] == len(r["rendered_text"]) // 4
        assert r["truncated"] == 0 and r["built_at"]
        assert c.duration_min == EXPECTED[sid][2], "the timeline and the sessions row agree on time to finish"


def test_dw1_analyze_refuses_a_missing_analysis_db(env, capsys):
    assert tutor("analyze") == 1
    assert not (env / "analysis.db").exists(), "analyze must not create an unmigrated database"
    assert "migrate" in capsys.readouterr().err


def test_dw1_analyze_refuses_an_unmigrated_db(env, capsys):
    sqlite3.connect(env / "analysis.db").close()   # exists, but no schema
    assert tutor("analyze") == 1
    assert "migrate" in capsys.readouterr().err
    assert q(env, "SELECT name FROM sqlite_master WHERE type='table'") == []


def test_dw1_one_transaction_and_the_budget_comes_from_config(migrated, monkeypatch):
    # A and B fit 600 est. tokens; D (two ≈5,000-char snapshots, opened + final) can't, so D fails
    # after A and B were condensed. Nothing may be written.
    monkeypatch.setenv("TUTOR__CONDENSER__TOKEN_BUDGET", "600")
    assert tutor("analyze") == 1
    for table in ("problems", "sessions", "condensed_timelines"):
        assert q(migrated, f"SELECT count(*) AS n FROM {table}") == [{"n": 0}], table


# ---------------------------------------------------------------- Done-when 2: idempotent upsert


def _snapshot_rows(tmp_path):
    sessions = q(tmp_path, "SELECT * FROM sessions ORDER BY session_id")
    timelines = q(tmp_path, "SELECT * FROM condensed_timelines ORDER BY session_id")
    for r in sessions:
        r.pop("loaded_at")
    for r in timelines:
        r.pop("built_at")
    return sessions, timelines, q(tmp_path, "SELECT * FROM problems")


def test_dw2_a_second_run_leaves_identical_rows(analyzed):
    before = _snapshot_rows(analyzed)
    assert tutor("analyze") == 0
    assert _snapshot_rows(analyzed) == before


def test_dw2_a_new_submit_updates_the_stored_session(analyzed):
    con = sqlite3.connect(analyzed / "capture.db")
    con.execute("INSERT INTO judge_events (session_id, ts, kind, status, tests_passed, tests_total, submission_id)"
                " VALUES (?, ?, 'submit', 'Accepted', 2, 2, '300')", (B, ts(B0, 7)))
    con.commit()
    con.close()
    assert tutor("analyze") == 0
    [r] = q(analyzed, "SELECT * FROM sessions WHERE session_id = ?", B)
    assert (r["status"], r["status_source"], r["time_to_finish_min"], r["submit_count"]) == \
        ("passed", "capture_submit", 7.0, 1)
    assert q(analyzed, "SELECT count(*) AS n FROM sessions") == [{"n": 3}], "updated in place, not duplicated"


# ---------------------------------------------------------------- Done-when 3: pipeline.jsonl


def test_dw3_one_log_outcome_per_session(analyzed):
    lines = log(analyzed)
    by_event = {}
    for x in lines:
        by_event.setdefault(x["event"], []).append(x)
    assert sorted(x["session_id"] for x in by_event.get("session_loaded", [])) == sorted([A, B, D])
    assert sorted(x["session_id"] for x in by_event.get("session_condensed", [])) == sorted([A, B, D])
    [ex] = by_event["session_excluded"]
    assert (ex["session_id"], ex["reason"]) == (C, "no_activity")
    run_ids = {x["run_id"] for x in lines if x["event"] in ("session_loaded", "session_condensed", "session_excluded")}
    assert len(run_ids) == 1, "one analyze run, one run id"


# ---------------------------------------------------------------- Done-when 4: rebuild-timelines


def test_dw4_rebuild_rewrites_every_timeline(analyzed):
    con = sqlite3.connect(analyzed / "analysis.db")
    con.execute("UPDATE condensed_timelines SET rendered_text = 'stale', est_tokens = 1")
    con.commit()
    con.close()
    assert tutor("rebuild-timelines") == 0
    for r in q(analyzed, "SELECT * FROM condensed_timelines"):
        assert r["rendered_text"] != "stale" and r["est_tokens"] == len(r["rendered_text"]) // 4


def test_dw4_an_orphaned_timeline_is_kept_and_logged(analyzed):
    con = sqlite3.connect(analyzed / "capture.db")   # the test's own capture file, not real data
    con.execute("DELETE FROM judge_events WHERE session_id = ?", (B,))
    con.execute("DELETE FROM snapshots WHERE session_id = ?", (B,))
    con.execute("DELETE FROM sessions WHERE id = ?", (B,))
    con.commit()
    con.close()
    [before] = q(analyzed, "SELECT * FROM condensed_timelines WHERE session_id = ?", B)
    assert tutor("rebuild-timelines") == 0
    assert q(analyzed, "SELECT * FROM condensed_timelines WHERE session_id = ?", B) == [before]
    assert [x["session_id"] for x in log(analyzed) if x["event"] == "timeline_orphaned"] == [B]


def test_dw4_a_failed_rebuild_changes_nothing(analyzed, monkeypatch):
    before = q(analyzed, "SELECT * FROM condensed_timelines ORDER BY session_id")
    monkeypatch.setenv("TUTOR__CONDENSER__TOKEN_BUDGET", "600")   # D can't fit, after A and B rebuilt
    assert tutor("rebuild-timelines") == 1
    assert q(analyzed, "SELECT * FROM condensed_timelines ORDER BY session_id") == before


# ---------------------------------------------------------------- Done-when 5: check


def _analysis_row(tmp_path, sid, version):
    con = sqlite3.connect(tmp_path / "analysis.db")
    con.execute("INSERT INTO session_analysis (session_id, condenser_version, updated_at) VALUES (?, ?, ?)",
                (sid, version, "2026-11-03T00:00:00Z"))
    con.commit()
    con.close()


def test_dw5_check_passes_with_no_analysis_rows(analyzed):
    assert tutor("check") == 0


def test_dw5_check_passes_when_versions_match(analyzed):
    _analysis_row(analyzed, A, "c1")
    assert tutor("check") == 0


def test_dw5_check_fails_and_names_a_stale_session(analyzed, capsys):
    _analysis_row(analyzed, A, "c1")
    _analysis_row(analyzed, D, "c0")
    capsys.readouterr()
    assert tutor("check") == 1
    out = capsys.readouterr()
    text = out.out + out.err
    assert D in text and A not in text


# ---------------------------------------------------------------- Done-when 6: capture untouched, no LLM columns


def test_dw6_the_capture_db_is_byte_identical(migrated):
    capture = migrated / "capture.db"
    before = sha(capture)
    assert tutor("analyze") == 0
    assert tutor("rebuild-timelines") == 0
    assert tutor("check") == 0
    assert sha(capture) == before


def test_dw6_analyze_writes_no_session_analysis_rows(analyzed):
    for table in ("session_analysis", "session_algorithms", "field_provenance"):
        assert q(analyzed, f"SELECT count(*) AS n FROM {table}") == [{"n": 0}], table


# ---------------------------------------------------------------- --since


def test_since_keeps_sessions_from_that_local_date_on(migrated):
    assert tutor("analyze", "--since", "2026-11-02") == 0
    assert [r["session_id"] for r in q(migrated, "SELECT session_id FROM sessions")] == [D]
