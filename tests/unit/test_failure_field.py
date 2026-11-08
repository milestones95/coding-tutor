"""Unit tests for the failure field's prompt variables (builder-owned, T-026)."""

from datetime import UTC, datetime

T0 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)


def _session(verdict, error=None):
    from tutor.models import Problem, Session, Snapshot, SubmitEvent

    ev = [SubmitEvent(ts=T0, verdict=verdict, tests_passed=3, tests_total=9, error_detail=error,
                      source="capture_submit")] if verdict else []
    return Session(session_id="u", problem=Problem(slug="p", title="P", difficulty="Easy", tags=[], description=None),
                   snapshots=[Snapshot(ts=T0, code="x", language="python3")], events=ev, submit_capture_reliable=True)


def _vars(s, tmp_path):
    from tutor.config import load_settings
    from tutor.fields.deterministic import status
    from tutor.fields.failure import failure_rule, variables

    settings = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path)}, dotenv_path=tmp_path / "x")
    st = status(s, settings=settings, run_id="u")
    return variables(s, st, failure_rule(st.status))


def test_outcome_names_verdict_counts_and_truncated_error(tmp_path):
    v = _vars(_session("Runtime Error", "E" * 900), tmp_path)
    assert v["outcome"].startswith("Final submit verdict: Runtime Error, 3/9 tests passed. Error: ")
    assert v["outcome"].count("E") <= 501 + 10
    assert v["decided"] == "Decide the type from the timeline."


def test_too_slow_is_given_to_the_model_as_decided(tmp_path):
    assert "too_slow" in _vars(_session("Time Limit Exceeded"), tmp_path)["decided"]


def test_not_submitted_outcome(tmp_path):
    assert _vars(_session(None), tmp_path)["outcome"].startswith("Not submitted")
