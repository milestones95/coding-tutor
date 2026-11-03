"""Acceptance tests for T-001: fix submit capture in the extension.

Tester-owned (`/test write T-001`, 2026-11-02). Done-when, from docs/tracker.md:
1. Written finding: logged in the tracker (page-hook.js:53, the `/v2/` segment); not a test.
2. On a real Submit, exactly one `judge_events` row: kind='submit', numeric submission_id,
   ts = result arrival, status = LeetCode's verdict text, tests_passed, tests_total,
   error_detail for failures. Only the final poll is recorded; repeat polls add no duplicates.
   The hook half is in tests/contract/capture/submit_capture.test.ts; here the real ingest
   server, fed what the relay sends, is checked end to end on a temp DB.
3. Three deliberate submits (Accepted, Wrong Answer, Time Limit Exceeded), checked with
   scripts/discovery/17_t001_submit_rows.sql: `live_capture`, run with -m live_capture.
4. No LeetCode user profile data stored.
5. `capture.submits_reliable_since` proposed: a note the human confirms in the task log.
"""

import json
import os
import re
import signal
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
UX = REPO / "ux-extension"
FIX = REPO / "evals" / "fixtures" / "capture"
LIVE_DB = REPO / "data" / "capture.db"
QUERY = REPO / "scripts" / "discovery" / "17_t001_submit_rows.sql"
PORT = 7792  # never 7777: the human's real server runs there
SLUG = "t001-probe"


def fixture(name: str) -> dict:
    return json.loads((FIX / name).read_text())


def submit_url(sid: str) -> str:
    return f"https://leetcode.com/submissions/detail/{sid}/v2/check/"


@pytest.fixture
def server(tmp_path):
    assert (UX / "node_modules").is_dir(), "run `npm --prefix ux-extension install` first"
    db = tmp_path / "probe.db"
    env = {k: v for k, v in os.environ.items() if k != "PORT" and not k.startswith("LCA_")}
    env.update(PORT=str(PORT), LCA_DB=str(db))
    log = (tmp_path / "server.log").open("w")
    proc = subprocess.Popen(["npm", "--prefix", str(UX), "start"], cwd=REPO, env=env,
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    base = f"http://127.0.0.1:{PORT}"
    try:
        deadline = time.time() + 30
        while True:
            try:
                with urllib.request.urlopen(f"{base}/health", timeout=1):
                    break
            except (urllib.error.URLError, OSError):
                if proc.poll() is not None or time.time() > deadline:
                    log.flush()
                    pytest.fail((tmp_path / "server.log").read_text()[-2000:])
                time.sleep(0.3)
        yield base, db
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        proc.wait(timeout=10)
        log.close()


def post(base: str, event: dict) -> None:
    req = urllib.request.Request(f"{base}/events", data=json.dumps(event).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        assert json.loads(r.read())["ok"] is True


def judge_event(data: dict, ts: str) -> dict:
    """What relay.js forwards for a hook-captured result (ts = when it arrived)."""
    return {"type": "judge", "slug": SLUG, "ts": ts, "url": submit_url(data["submission_id"]),
            "data": data, "code": "class Solution: pass\n", "language": "python3"}


def start(base: str) -> None:
    post(base, {"type": "problem_view", "slug": SLUG, "ts": "2026-01-06T09:00:00.000Z",
                "problem": {"title": "T001 Probe", "difficulty": "Medium", "tags": ["dynamic-programming"]}})
    post(base, {"type": "snapshot", "slug": SLUG, "ts": "2026-01-06T09:00:05.000Z", "code": "x = 1\n"})


def submits(db: Path) -> list[dict]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("SELECT * FROM judge_events WHERE kind = 'submit' ORDER BY ts")]
    con.close()
    return rows


# ---------------------------------------------------------------- Done-when 2


@pytest.mark.parametrize("name,verdict,passed,failed", [
    ("submit_check_accepted.json", "Accepted", 191, False),
    ("submit_check_wrong_answer.json", "Wrong Answer", 40, True),
    ("submit_check_tle.json", "Time Limit Exceeded", 120, True),
    ("submit_check_output_limit.json", "Output Limit Exceeded", 68, True),
])
def test_dw2_one_submit_row_with_every_field(server, name, verdict, passed, failed):
    base, db = server
    start(base)
    data = fixture(name)
    post(base, judge_event(data, "2026-01-06T09:10:00.000Z"))
    rows = submits(db)
    assert len(rows) == 1, rows
    r = rows[0]
    assert r["submission_id"] == data["submission_id"] and re.fullmatch(r"\d+", r["submission_id"])
    assert r["ts"] == "2026-01-06T09:10:00.000Z", "ts must be when the result arrived"
    assert r["status"] == verdict, "status is LeetCode's verdict text, verbatim"
    assert (r["tests_passed"], r["tests_total"]) == (passed, 191)
    assert (r["error_detail"] is not None) == failed


def test_dw2_repeat_final_poll_of_a_failed_submit_is_stored_once(server):
    base, db = server
    start(base)
    data = fixture("submit_check_wrong_answer.json")
    post(base, judge_event(data, "2026-01-06T09:10:00.000Z"))
    post(base, judge_event(data, "2026-01-06T09:10:01.000Z"))
    rows = submits(db)
    assert len(rows) == 1 and rows[0]["ts"] == "2026-01-06T09:10:00.000Z"


def test_dw2_repeat_final_poll_of_an_accepted_submit_is_stored_once(server):
    """An Accepted submit ends the session; a repeat of the same result a second later must not
    open a new session holding a second copy."""
    base, db = server
    start(base)
    data = fixture("submit_check_accepted.json")
    post(base, judge_event(data, "2026-01-06T09:10:00.000Z"))
    post(base, judge_event(data, "2026-01-06T09:10:01.000Z"))
    rows = submits(db)
    assert len(rows) == 1, f"{len(rows)} rows for one submission: {[r['session_id'] for r in rows]}"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    n_sessions = con.execute("SELECT COUNT(*) FROM sessions WHERE slug = ?", (SLUG,)).fetchone()[0]
    con.close()
    assert n_sessions == 1, "a repeated result opened a phantom session"


# ---------------------------------------------------------------- Done-when 4


def test_dw4_no_user_profile_data_is_stored(server):
    base, db = server
    start(base)
    post(base, judge_event(fixture("submit_check_with_user_block.json"), "2026-01-06T09:10:00.000Z"))
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    leaked = []
    for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
        for row in con.execute(f"SELECT * FROM {table}"):
            if any(isinstance(v, str) and "SENTINEL" in v for v in row):
                leaked.append(table)
    con.close()
    assert not leaked, f"LeetCode user data stored in: {sorted(set(leaked))}"


# ---------------------------------------------------------------- Done-when 3 (real browser)


@pytest.mark.live_capture
def test_dw3_three_deliberate_submits_were_captured():
    assert QUERY.is_file()
    con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(QUERY.read_text())]
    con.close()
    by_status = {r["status"]: r for r in rows}
    for verdict in ("Accepted", "Wrong Answer", "Time Limit Exceeded"):
        assert verdict in by_status, f"no captured '{verdict}' submit yet — submit one on LeetCode"
        r = by_status[verdict]
        assert re.fullmatch(r"\d+", r["submission_id"] or ""), r
        assert r["tests_passed"] is not None and r["tests_total"] is not None, r
        assert bool(r["has_error_detail"]) == (verdict != "Accepted"), r
    ids = [r["submission_id"] for r in rows]
    assert len(ids) == len(set(ids)), "the same submission was stored more than once"
