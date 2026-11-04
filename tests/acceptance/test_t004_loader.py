"""Acceptance tests for T-004: inference-side data models + read-only capture loader.

Tester-owned (`/test write T-004`, 2026-11-03). One or more tests per Done-when condition.
Interfaces, agreed with the human because the architecture doesn't name them (D-024):

    tutor.models: Problem, Snapshot, RunEvent, SubmitEvent, Session, Verdict
    tutor.capture.loader.CaptureLoader(path, *, mode: "ro" | "immutable", settings, run_id=None)
        .iter_sessions(since: datetime | None = None) -> Iterator[Session]   # by started_at
        .load_session(session_id) -> Session        # LookupError if unknown or excluded
    tutor.capture.loader.VerdictConflict, CaptureFormatError
    exclusions -> log event `session_excluded` {session_id, reason: no_activity | human_exclude}
                  in <paths.logs>/pipeline.jsonl

Decisions the human made for these tests (2026-11-03):
- `SubmitEvent.verdict` is the verdict text verbatim (str); status mapping (M1) handles text
  it doesn't know.
- `submit_capture_reliable` compares the session's start date in `time.timezone` with
  `capture.submits_reliable_since`.
- A captured submit and a verdicts.csv row that agree: the captured one is kept, the CSV row
  is dropped. A disagreement raises VerdictConflict. CSV rows match by session id only.

Done-when 3 reads the human's real files in data/, so it is `live_capture` (run with
`-m live_capture`); everything else uses tiny DBs built in the test (tests/_capture_fixture.py).
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from _capture_fixture import PROBLEM, SENTINEL, build, write_verdicts
from tutor.config import REPO_ROOT, load_settings

T0 = "2026-11-01T10:00:00.000Z"


def ts(minutes: float) -> str:
    t = datetime(2026, 11, 1, 10, 0, tzinfo=UTC) + timedelta(minutes=minutes)
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def settings_for(tmp_path, *, live_db=None, verdicts=None, since=None):
    env = {
        "TUTOR__PATHS__CAPTURE_DB": str(live_db or tmp_path / "live-not-used.db"),
        "TUTOR__PATHS__VERDICTS": str(verdicts or tmp_path / "no-verdicts.csv"),
        "TUTOR__PATHS__LOGS": str(tmp_path / "logs"),
    }
    if since:
        env["TUTOR__CAPTURE__SUBMITS_RELIABLE_SINCE"] = since
    return load_settings(env=env, dotenv_path=tmp_path / "none.env")


def loader(tmp_path, db, *, mode="immutable", **kw):
    from tutor.capture.loader import CaptureLoader

    return CaptureLoader(db, mode=mode, settings=settings_for(tmp_path, **kw))


def excluded(tmp_path) -> dict[str, str]:
    log = tmp_path / "logs" / "pipeline.jsonl"
    rows = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return {r["session_id"]: r["reason"] for r in rows if r["event"] == "session_excluded"}


def one_session_db(tmp_path, *, sid="s-1", judge_events=(), n_snapshots=3, **kw):
    snaps = [{"session_id": sid, "ts": ts(i), "code": f"x = {i}\n"} for i in range(n_snapshots)]
    return build(tmp_path / "cap.db", sessions=[{"id": sid, "started_at": T0}], snapshots=snaps,
                 judge_events=[{"session_id": sid, **j} for j in judge_events], **kw)


# ---------------------------------------------------------------- Done-when 1: models


def test_dw1_models_are_frozen_typed_and_validated():
    from tutor.models import Problem, RunEvent, Session, Snapshot, SubmitEvent

    p = Problem(slug="a", title="A", difficulty="Easy", tags=["array"], description=None)
    with pytest.raises(ValidationError):
        Problem(slug="a", title="A", difficulty="Insane", tags=[], description=None)
    snap = Snapshot(ts=datetime(2026, 11, 1, 10, tzinfo=UTC), code="x", language="python3")
    with pytest.raises(ValidationError, match="(?i)timezone"):
        Snapshot(ts=datetime(2026, 11, 1, 10), code="x", language="python3")  # naive: not UTC-aware
    run = RunEvent(ts=snap.ts, status="Passed sample tests", tests_passed=3, tests_total=3, error_detail=None)
    sub = SubmitEvent(ts=None, verdict="Accepted", tests_passed=5, tests_total=5, error_detail=None,
                      source="human_resubmit")
    s = Session(session_id="s", problem=p, snapshots=[snap], events=[run, sub], submit_capture_reliable=False)
    with pytest.raises(ValidationError):
        s.session_id = "other"
    with pytest.raises(ValidationError):
        Session(session_id="s", problem=p, snapshots=[], events=[], submit_capture_reliable=False)
    with pytest.raises(ValidationError):
        SubmitEvent(ts=None, verdict="Accepted", tests_passed=1, tests_total=1, error_detail=None, source="guess")


def test_dw1_verdict_is_kept_verbatim_even_when_unlisted():
    from tutor.models import SubmitEvent, Verdict

    assert {v.value for v in Verdict} == {
        "Accepted", "Wrong Answer", "Time Limit Exceeded", "Runtime Error", "Memory Limit Exceeded",
        "Output Limit Exceeded", "Compile Error",
    }
    e = SubmitEvent(ts=None, verdict="Some New Verdict", tests_passed=None, tests_total=None,
                    error_detail=None, source="capture_submit")
    assert e.verdict == "Some New Verdict"


def test_dw1_final_submit_is_the_last_submit_event():
    from tutor.models import Problem, RunEvent, Session, Snapshot, SubmitEvent

    t = datetime(2026, 11, 1, 10, tzinfo=UTC)
    p = Problem(slug="a", title="A", difficulty="Easy", tags=[], description=None)
    snap = Snapshot(ts=t, code="x", language="python3")
    wa = SubmitEvent(ts=t, verdict="Wrong Answer", tests_passed=1, tests_total=5, error_detail="e",
                     source="capture_submit")
    ac = SubmitEvent(ts=t + timedelta(minutes=2), verdict="Accepted", tests_passed=5, tests_total=5,
                     error_detail=None, source="capture_submit")
    run = RunEvent(ts=t + timedelta(minutes=3), status="Passed sample tests", tests_passed=3, tests_total=3,
                   error_detail=None)
    s = Session(session_id="s", problem=p, snapshots=[snap], events=[wa, ac, run], submit_capture_reliable=True)
    assert s.final_submit == ac
    assert Session(session_id="s", problem=p, snapshots=[snap], events=[run],
                   submit_capture_reliable=True).final_submit is None


# ---------------------------------------------------------------- Done-when 2: read-only, caller's mode


@pytest.mark.parametrize("mode", ["ro", "immutable"])
def test_dw2_loads_a_session_in_either_mode(tmp_path, mode):
    db = one_session_db(tmp_path, judge_events=[
        {"ts": ts(1.5), "kind": "run", "status": "Wrong Answer (sample tests)", "tests_passed": 1,
         "tests_total": 3, "error_detail": "Output: 1 | Expected: 2", "submission_id": "runcode_1"},
        {"ts": ts(2.5), "kind": "submit", "status": "Accepted", "tests_passed": 9, "tests_total": 9,
         "submission_id": "100"},
    ])
    [s] = list(loader(tmp_path, db, mode=mode).iter_sessions())
    assert s.session_id == "s-1"
    assert (s.problem.slug, s.problem.title, s.problem.difficulty) == (PROBLEM["slug"], PROBLEM["title"], "Medium")
    assert s.problem.tags == PROBLEM["tags"] and s.problem.description == PROBLEM["description"]
    assert [n.code for n in s.snapshots] == ["x = 0\n", "x = 1\n", "x = 2\n"]
    run, sub = s.events
    assert (run.kind, run.status, run.tests_passed, run.tests_total, run.error_detail) == (
        "run", "Wrong Answer (sample tests)", 1, 3, "Output: 1 | Expected: 2")
    assert (sub.kind, sub.verdict, sub.tests_passed, sub.tests_total, sub.source) == (
        "submit", "Accepted", 9, 9, "capture_submit")
    assert sub.ts == datetime(2026, 11, 1, 10, 2, 30, tzinfo=UTC)
    assert s.final_submit == sub


def test_dw2_snapshots_and_events_come_back_sorted_by_time(tmp_path):
    snaps = [{"id": i, "session_id": "s-1", "ts": ts(m), "code": f"v{m}"} for i, m in [(1, 3), (2, 1), (3, 2)]]
    events = [{"id": 1, "session_id": "s-1", "ts": ts(2.5), "kind": "run", "status": "Passed sample tests",
               "submission_id": "runcode_b"},
              {"id": 2, "session_id": "s-1", "ts": ts(1.5), "kind": "run", "status": "Runtime Error",
               "submission_id": "runcode_a"}]
    db = build(tmp_path / "cap.db", sessions=[{"id": "s-1", "started_at": T0}], snapshots=snaps,
               judge_events=events)
    [s] = list(loader(tmp_path, db).iter_sessions())
    assert [n.code for n in s.snapshots] == ["v1", "v2", "v3"]
    assert [e.status for e in s.events] == ["Runtime Error", "Passed sample tests"]


def test_dw2_load_session_and_since_filter(tmp_path):
    sessions = [{"id": "early", "started_at": ts(0)}, {"id": "late", "started_at": ts(60)}]
    snaps = [{"session_id": sid, "ts": ts(base + i), "code": f"{sid}{i}"}
             for sid, base in [("early", 0), ("late", 60)] for i in range(2)]
    db = build(tmp_path / "cap.db", sessions=sessions, snapshots=snaps)
    ld = loader(tmp_path, db)
    assert [s.session_id for s in ld.iter_sessions()] == ["early", "late"]
    assert [s.session_id for s in ld.iter_sessions(since=datetime(2026, 11, 1, 10, 30, tzinfo=UTC))] == ["late"]
    assert ld.load_session("late").session_id == "late"
    with pytest.raises(LookupError):
        ld.load_session("no-such-session")


def test_dw2_immutable_on_the_live_capture_path_is_refused(tmp_path):
    db = one_session_db(tmp_path)
    from tutor.capture.loader import CaptureLoader

    s = settings_for(tmp_path, live_db=db)
    with pytest.raises(ValueError, match="immutable"):
        CaptureLoader(db, mode="immutable", settings=s)
    # the same file under another spelling of its path is still the live file
    with pytest.raises(ValueError, match="immutable"):
        CaptureLoader(tmp_path / "." / "sub" / ".." / db.name, mode="immutable", settings=s)
    # mode=ro on the live file is how the pipeline reads it
    assert [x.session_id for x in CaptureLoader(db, mode="ro", settings=s).iter_sessions()] == ["s-1"]


def test_dw2_unknown_mode_is_refused(tmp_path):
    db = one_session_db(tmp_path)
    with pytest.raises(ValueError):
        loader(tmp_path, db, mode="rw")


def test_dw2_never_reads_the_old_analyzer_output(tmp_path):
    """attempts*, attempt_gaps and sessions.analysis_* hold a sentinel; none of it may reach a Session."""
    db = one_session_db(tmp_path, judge_events=[
        {"ts": ts(1), "kind": "run", "status": "Passed sample tests", "submission_id": "runcode_1"}])
    for s in loader(tmp_path, db).iter_sessions():
        assert SENTINEL not in s.model_dump_json()


def test_dw2_session_ids_in_the_csv_match_by_session_not_problem(tmp_path):
    """An old session's hand verdict must not touch a new session on the same problem."""
    sessions = [{"id": "old", "started_at": ts(0)}, {"id": "new", "started_at": ts(60)}]
    snaps = [{"session_id": sid, "ts": ts(base + i), "code": f"{sid}{i}"}
             for sid, base in [("old", 0), ("new", 60)] for i in range(2)]
    db = build(tmp_path / "cap.db", sessions=sessions, snapshots=snaps, judge_events=[
        {"session_id": "new", "ts": ts(62), "kind": "submit", "status": "Wrong Answer", "tests_passed": 3,
         "tests_total": 9, "error_detail": "Input: x", "submission_id": "200"}])
    csv = write_verdicts(tmp_path / "v.csv", [{"session_id": "old", "verdict": "Accepted", "passed": 9, "total": 9}])
    got = {s.session_id: s.final_submit for s in loader(tmp_path, db, verdicts=csv).iter_sessions()}
    assert (got["old"].verdict, got["old"].source) == ("Accepted", "human_resubmit")
    assert (got["new"].verdict, got["new"].source) == ("Wrong Answer", "capture_submit")


@pytest.mark.parametrize("started_at,since,expected", [
    ("2026-11-04T03:30:00.000Z", "2026-11-04", False),   # 22:30 on Nov 3 in New York
    ("2026-11-04T05:30:00.000Z", "2026-11-04", True),    # 00:30 on Nov 4 in New York
    ("2026-11-05T12:00:00.000Z", None, False),           # unset -> never reliable
])
def test_dw2_submit_capture_reliable_uses_the_configured_timezone(tmp_path, started_at, since, expected):
    t = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    snaps = [{"session_id": "s", "ts": (t + timedelta(seconds=10 * i)).isoformat().replace("+00:00", "Z"),
              "code": f"{i}"} for i in range(2)]
    db = build(tmp_path / "cap.db", sessions=[{"id": "s", "started_at": started_at}], snapshots=snaps)
    [s] = list(loader(tmp_path, db, since=since).iter_sessions())
    assert s.submit_capture_reliable is expected


# ---------------------------------------------------------------- non-attempts (rule for Done-when 3)


def test_dw3_non_attempts_are_excluded_and_logged_with_a_reason(tmp_path):
    sessions = [{"id": i, "started_at": ts(n)} for n, i in enumerate(["opened", "one-snap", "real", "one-run", "human"])]
    snaps = ([{"session_id": "one-snap", "ts": ts(1), "code": "stub"}]
             + [{"session_id": "real", "ts": ts(2 + i / 10), "code": f"r{i}"} for i in range(3)]
             + [{"session_id": "one-run", "ts": ts(3), "code": "a"}]
             + [{"session_id": "human", "ts": ts(4 + i / 10), "code": f"h{i}"} for i in range(5)])
    runs = [{"session_id": "one-run", "ts": ts(3.5), "kind": "run", "status": "Runtime Error",
             "submission_id": "runcode_x"}]
    db = build(tmp_path / "cap.db", sessions=sessions, snapshots=snaps, judge_events=runs)
    csv = write_verdicts(tmp_path / "v.csv", [{"session_id": "human", "note": "EXCLUDE: never attempted (human)"}])
    kept = [s.session_id for s in loader(tmp_path, db, verdicts=csv).iter_sessions()]
    assert kept == ["real", "one-run"], "≤1 snapshot and no judge events = non-attempt; a run makes it real"
    assert excluded(tmp_path) == {"opened": "no_activity", "one-snap": "no_activity", "human": "human_exclude"}
    with pytest.raises(LookupError):
        loader(tmp_path, db, verdicts=csv).load_session("human")


# ---------------------------------------------------------------- Done-when 4: verdicts.csv


def test_dw4_csv_verdict_becomes_a_backfilled_submit_listed_last(tmp_path):
    db = one_session_db(tmp_path, judge_events=[
        {"ts": ts(2), "kind": "run", "status": "Passed sample tests", "submission_id": "runcode_1"}])
    csv = write_verdicts(tmp_path / "v.csv", [{"session_id": "s-1", "verdict": "Wrong Answer", "passed": 59, "total": 90}])
    [s] = list(loader(tmp_path, db, verdicts=csv).iter_sessions())
    assert [e.kind for e in s.events] == ["run", "submit"]
    sub = s.final_submit
    assert (sub.ts, sub.verdict, sub.tests_passed, sub.tests_total, sub.source) == (
        None, "Wrong Answer", 59, 90, "human_resubmit")


def test_dw4_conflicting_captured_verdict_raises(tmp_path):
    db = one_session_db(tmp_path, judge_events=[
        {"ts": ts(2), "kind": "submit", "status": "Wrong Answer", "tests_passed": 3, "tests_total": 9,
         "error_detail": "Input: x", "submission_id": "100"}])
    csv = write_verdicts(tmp_path / "v.csv", [{"session_id": "s-1", "verdict": "Accepted", "passed": 9, "total": 9}])
    from tutor.capture.loader import VerdictConflict

    with pytest.raises(VerdictConflict, match="s-1"):
        list(loader(tmp_path, db, verdicts=csv).iter_sessions())


def test_dw4_agreeing_captured_verdict_wins_and_the_csv_row_is_dropped(tmp_path):
    db = one_session_db(tmp_path, judge_events=[
        {"ts": ts(2), "kind": "submit", "status": "Accepted", "tests_passed": 9, "tests_total": 9,
         "submission_id": "100"}])
    csv = write_verdicts(tmp_path / "v.csv", [{"session_id": "s-1", "verdict": "Accepted", "passed": 9, "total": 9}])
    [s] = list(loader(tmp_path, db, verdicts=csv).iter_sessions())
    submits = [e for e in s.events if e.kind == "submit"]
    assert len(submits) == 1 and submits[0].source == "capture_submit" and submits[0].ts is not None


def test_dw4_conflict_is_judged_on_the_last_captured_submit(tmp_path):
    db = one_session_db(tmp_path, judge_events=[
        {"ts": ts(2), "kind": "submit", "status": "Wrong Answer", "tests_passed": 3, "tests_total": 9,
         "error_detail": "Input: x", "submission_id": "100"},
        {"ts": ts(3), "kind": "submit", "status": "Accepted", "tests_passed": 9, "tests_total": 9,
         "submission_id": "101"}])
    csv = write_verdicts(tmp_path / "v.csv", [{"session_id": "s-1", "verdict": "Accepted", "passed": 9, "total": 9}])
    [s] = list(loader(tmp_path, db, verdicts=csv).iter_sessions())
    assert [e.verdict for e in s.events if e.kind == "submit"] == ["Wrong Answer", "Accepted"]


def test_dw4_missing_verdicts_file_means_no_backfill(tmp_path):
    db = one_session_db(tmp_path)
    [s] = list(loader(tmp_path, db, verdicts=tmp_path / "absent.csv").iter_sessions())
    assert s.final_submit is None


# ---------------------------------------------------------------- Done-when 5: bad timestamps


@pytest.mark.parametrize("table", ["snapshots", "judge_events", "sessions"])
def test_dw5_bad_timestamp_names_session_table_and_row(tmp_path, table):
    snaps = [{"id": 41, "session_id": "s-bad", "ts": ts(0), "code": "a"},
             {"id": 42, "session_id": "s-bad", "ts": "yesterday-ish" if table == "snapshots" else ts(1), "code": "b"}]
    events = [{"id": 77, "session_id": "s-bad", "ts": "not a time" if table == "judge_events" else ts(2),
               "kind": "run", "status": "Passed sample tests", "submission_id": "runcode_1"}]
    started = "31/10/2026 10:00" if table == "sessions" else T0
    db = build(tmp_path / "cap.db", sessions=[{"id": "s-bad", "started_at": started}], snapshots=snaps,
               judge_events=events)
    from tutor.capture.loader import CaptureFormatError

    with pytest.raises(CaptureFormatError) as err:
        list(loader(tmp_path, db).iter_sessions())
    msg = str(err.value)
    assert "s-bad" in msg and table in msg
    if table != "sessions":
        assert {"snapshots": "42", "judge_events": "77"}[table] in msg


def test_dw5_good_timestamps_load_as_utc_aware(tmp_path):
    db = one_session_db(tmp_path)
    [s] = list(loader(tmp_path, db).iter_sessions())
    assert all(n.ts.utcoffset() == timedelta(0) for n in s.snapshots)
    assert s.snapshots[0].ts == datetime(2026, 11, 1, 10, 0, tzinfo=UTC)


# ---------------------------------------------------------------- Done-when 3: the frozen copy (real data)

REAL_SESSIONS = {  # data/labels/verdicts.csv, human-entered 2026-11-02 (D-005)
    "ebd80323-3d5b-4504-b5cd-1cff39c7ae82": ("Accepted", 66, 66),
    "010fa987-3416-4209-a723-37669784b618": ("Accepted", 63, 63),
    "81224169-f24d-4b6a-8675-65226df37630": ("Wrong Answer", 59, 90),
    "1db561ab-050a-4e93-bef8-294788cc16ba": ("Accepted", 90, 90),
    "68f118c2-bbd5-4bdf-be5d-dc3553b5e61c": ("Accepted", 362, 362),
    "cdacb216-6f7c-40b1-8f59-1e3ae5af32da": ("Accepted", 73, 73),
    "be762faa-e34d-4c95-b252-5839ce95f301": ("Accepted", 191, 191),
    "70241a81-0ba9-4c2f-9348-690c26dfe944": ("Accepted", 66, 66),
}
HUMAN_EXCLUDED = "63b86d7c-9cbf-40b0-ba60-53e2a925bc54"  # search-insert-position, opened, never attempted


@pytest.mark.live_capture
def test_dw3_frozen_copy_yields_the_8_real_sessions_and_logs_14_exclusions(tmp_path):
    from tutor.capture.loader import CaptureLoader

    s = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")
    ref = s.paths.eval_capture_db
    assert ref == REPO_ROOT / "data" / "reference" / "capture.db" and ref.is_file()
    before = hashlib.sha256(ref.read_bytes()).hexdigest()

    sessions = list(CaptureLoader(ref, mode="immutable", settings=s).iter_sessions())

    assert {x.session_id for x in sessions} == REAL_SESSIONS.keys()
    for x in sessions:
        f = x.final_submit
        assert (f.verdict, f.tests_passed, f.tests_total) == REAL_SESSIONS[x.session_id], x.session_id
        assert f.source == "human_resubmit" and f.ts is None
        assert x.submit_capture_reliable is False, "every frozen session predates the submit fix"
    ex = excluded(tmp_path)
    assert len(ex) == 14 and not ex.keys() & REAL_SESSIONS.keys()
    assert ex[HUMAN_EXCLUDED] == "human_exclude"
    assert set(ex.values()) == {"no_activity", "human_exclude"}
    assert hashlib.sha256(ref.read_bytes()).hexdigest() == before, "the frozen copy was modified"
