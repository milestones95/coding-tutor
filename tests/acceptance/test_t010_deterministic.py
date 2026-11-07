"""Acceptance tests for T-010: deterministic fields (architecture §4.2, §4.3, §5.1; D-014, D-019,
D-022, D-024).

Tester-owned (`/test write T-010`, 2026-11-03). Interfaces (D-036, human approved):

    tutor.models: Status, StatusSource      # StrEnums, values = §3.2 CHECK lists
    tutor.fields.deterministic:
        problem(session) -> Problem
        time_to_finish(session) -> float                               # minutes, 1 decimal
        attempted_at(session, *, settings) -> tuple[datetime, date]    # (first event UTC, local date)
        status(session, *, settings, run_id) -> StatusResult
    StatusResult: status, status_source, leetcode_verdict, tests_passed, tests_total
    An unmapped verdict → `unknown`, plus one `unmapped_verdict` line in <paths.logs>/pipeline.jsonl
    with `session_id` and `verdict`. It never raises.

Sessions are hand-built; local dates were checked against the IANA tz database.
"""

import ast
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from tutor.models import Problem, RunEvent, Session, Snapshot, SubmitEvent

REPO = Path(__file__).resolve().parents[2]
T0 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
PROBLEM = Problem(slug="sort-colors", title="Sort Colors", difficulty="Medium",
                  tags=["array", "two-pointers", "sorting"], description=None)


def at(minutes=0, seconds=0, base=T0):
    return base + timedelta(minutes=minutes, seconds=seconds)


def snap(t, code="x = 1"):
    return Snapshot(ts=t, code=code, language="python3")


def run(t, status="Passed sample tests"):
    return RunEvent(ts=t, status=status, tests_passed=2, tests_total=2, error_detail=None)


def sub(t, verdict="Accepted", passed=5, total=5, source="capture_submit"):
    return SubmitEvent(ts=t, verdict=verdict, tests_passed=passed, tests_total=total, error_detail=None,
                       source=source)


def session(snaps, events=(), *, reliable=True, sid="s1"):
    return Session(session_id=sid, problem=PROBLEM, snapshots=list(snaps), events=list(events),
                   submit_capture_reliable=reliable)


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def det():
    import tutor.fields.deterministic

    return tutor.fields.deterministic


def pipeline_log(tmp_path):
    path = tmp_path / "logs" / "pipeline.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


# ---------------------------------------------------------------- Done-when 1: problem


def test_dw1_problem_is_the_sessions_problem():
    p = det().problem(session([snap(at(0))]))
    assert (p.slug, p.title, p.difficulty, p.tags) == ("sort-colors", "Sort Colors", "Medium",
                                                       ["array", "two-pointers", "sorting"])


# ---------------------------------------------------------------- Done-when 2: time to finish


def test_dw2_time_to_finish_ends_at_the_last_captured_submit():
    # first event 10:00; submits at 7:00 and 12:30; then a run at 20:00 and more typing → 12.5
    s = session([snap(at(0)), snap(at(25), "x = 2")], [sub(at(7), "Wrong Answer"), sub(at(12, 30)), run(at(20))])
    assert det().time_to_finish(s) == 12.5


def test_dw2_without_a_captured_submit_it_ends_at_the_last_event():
    # last event is the run at 18:20 (the last snapshot is earlier); the backfilled submit has no time
    s = session([snap(at(0)), snap(at(9))], [run(at(18, 20)), sub(None, source="human_resubmit")], reliable=False)
    assert det().time_to_finish(s) == 18.3


def test_dw2_first_event_can_be_a_run_before_any_snapshot():
    s = session([snap(at(2)), snap(at(10))], [run(at(1))])
    assert det().time_to_finish(s) == 9.0


@pytest.mark.parametrize("s", [
    session([snap(at(0)), snap(at(25), "x = 2")], [sub(at(7), "Wrong Answer"), sub(at(12, 30)), run(at(20))]),
    session([snap(at(0)), snap(at(9))], [run(at(18, 20)), sub(None, source="human_resubmit")], reliable=False),
    session([snap(at(2)), snap(at(10))], [run(at(1))]),
    session([snap(at(0))]),
])
def test_dw2_time_to_finish_equals_the_condensers_duration(s):
    from tutor.condense import condense

    assert det().time_to_finish(s) == condense(s).duration_min


# ---------------------------------------------------------------- Done-when 3: attempted at


@pytest.mark.parametrize("utc,local", [
    ("2026-11-01T03:30:00+00:00", date(2026, 10, 31)),   # 23:30 EDT Oct 31: still the day before in New York
    ("2026-11-01T05:30:00+00:00", date(2026, 11, 1)),    # 01:30 EDT, before the clocks go back
    ("2026-11-01T06:30:00+00:00", date(2026, 11, 1)),    # 01:30 EST, the repeated hour (DST ends)
    ("2026-11-02T03:30:00+00:00", date(2026, 11, 1)),    # 22:30 EST Nov 1
    ("2026-11-03T01:30:00+00:00", date(2026, 11, 2)),    # 20:30 EST Nov 2: after 8 pm in New York
])
def test_dw3_attempted_at_is_the_first_event_and_its_new_york_date(settings, utc, local):
    start = datetime.fromisoformat(utc)
    s = session([snap(at(0, base=start)), snap(at(30, base=start))], [run(at(5, base=start))])
    when, day = det().attempted_at(s, settings=settings)
    assert when == start and when.utcoffset() == timedelta(0)
    assert day == local


def test_dw3_attempted_at_uses_the_earliest_event_not_the_first_snapshot(settings):
    s = session([snap(at(3))], [run(at(1))])
    assert det().attempted_at(s, settings=settings)[0] == at(1)


def test_dw3_the_timezone_comes_from_settings(tmp_path):
    from tutor.config import load_settings

    tokyo = load_settings(env={"TUTOR__TIME__TIMEZONE": "Asia/Tokyo"}, dotenv_path=tmp_path / "none.env")
    s = session([snap(datetime(2026, 11, 1, 20, 0, tzinfo=UTC))])   # 05:00 Nov 2 in Tokyo
    assert det().attempted_at(s, settings=tokyo)[1] == date(2026, 11, 2)


# ---------------------------------------------------------------- Done-when 4: status (§4.3)


@pytest.mark.parametrize("verdict,expected", [
    ("Accepted", "passed"),
    ("Wrong Answer", "failed_wrong_answer"),
    ("Time Limit Exceeded", "failed_too_slow"),
    ("Memory Limit Exceeded", "failed_too_slow"),
    ("Runtime Error", "failed_runtime_error"),
    ("Compile Error", "failed_runtime_error"),
    ("Output Limit Exceeded", "failed_output_limit"),
])
def test_dw4_status_table_row(settings, verdict, expected):
    r = det().status(session([snap(at(0))], [sub(at(5), verdict, 3, 9)]), settings=settings, run_id="r")
    assert (r.status, r.status_source) == (expected, "capture_submit")
    assert (r.leetcode_verdict, r.tests_passed, r.tests_total) == (verdict, 3, 9)


def test_dw4_an_unmapped_verdict_is_unknown_and_logged(tmp_path, settings):
    r = det().status(session([snap(at(0))], [sub(at(5), "Queue Overflow Exceeded")]), settings=settings, run_id="r9")
    assert (r.status, r.status_source, r.leetcode_verdict) == ("unknown", "capture_submit", "Queue Overflow Exceeded")
    [line] = [x for x in pipeline_log(tmp_path) if x["event"] == "unmapped_verdict"]
    assert (line["session_id"], line["verdict"], line["run_id"]) == ("s1", "Queue Overflow Exceeded", "r9")


def test_dw4_no_submit_when_capture_is_reliable_is_not_submitted(settings):
    r = det().status(session([snap(at(0))], [run(at(3))], reliable=True), settings=settings, run_id="r")
    assert (r.status, r.status_source) == ("not_submitted", "no_submit")
    assert (r.leetcode_verdict, r.tests_passed, r.tests_total) == (None, None, None)


def test_dw4_no_submit_when_capture_is_not_reliable_is_unknown(settings):
    r = det().status(session([snap(at(0))], [run(at(3))], reliable=False), settings=settings, run_id="r")
    assert (r.status, r.status_source) == ("unknown", "not_captured")


def test_dw4_the_final_submit_decides(settings):
    s = session([snap(at(0))], [sub(at(3), "Wrong Answer", 1, 5), sub(at(9), "Accepted", 5, 5)])
    r = det().status(s, settings=settings, run_id="r")
    assert (r.status, r.leetcode_verdict, r.tests_passed) == ("passed", "Accepted", 5)


def test_dw4_passing_runs_are_not_a_submit(settings):
    s = session([snap(at(0))], [run(at(1)), run(at(2), "Accepted")], reliable=True)
    assert det().status(s, settings=settings, run_id="r").status == "not_submitted"


def test_dw4_a_backfilled_verdict_is_human_resubmit(settings):
    s = session([snap(at(0))], [run(at(4)), sub(None, "Wrong Answer", 59, 90, source="human_resubmit")],
                reliable=False)
    r = det().status(s, settings=settings, run_id="r")
    assert (r.status, r.status_source, r.tests_passed, r.tests_total) == \
        ("failed_wrong_answer", "human_resubmit", 59, 90)


def test_dw4_status_enums_match_the_schema():
    from tutor.models import Status, StatusSource

    assert {s.value for s in Status} == {"passed", "failed_wrong_answer", "failed_too_slow", "failed_output_limit",
                                         "failed_runtime_error", "not_submitted", "unknown"}
    assert {s.value for s in StatusSource} == {"capture_submit", "human_resubmit", "no_submit", "not_captured"}


# ---------------------------------------------------------------- Done-when 5: submits_reliable_since


def test_dw5_tutor_toml_sets_submits_reliable_since(tmp_path):
    from tutor.config import load_settings

    assert load_settings(env={}, dotenv_path=tmp_path / "none.env").capture.submits_reliable_since == date(2026, 11, 4)


# ---------------------------------------------------------------- Done-when 6: no LLM


def test_dw6_deterministic_fields_never_touch_the_llm_layer():
    path = REPO / "src" / "tutor" / "fields" / "deterministic.py"
    tree = ast.parse(path.read_text())
    imported = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    imported += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not [m for m in imported if m == "tutor.llm" or m.startswith("tutor.llm.")]
