"""Builder unit tests for tutor.fields.deterministic internals (T-010)."""

from datetime import UTC, datetime

from tutor.config import load_settings
from tutor.fields.deterministic import STATUS_BY_VERDICT, status
from tutor.models import Problem, Session, Snapshot, Status, SubmitEvent, Verdict


def test_every_known_verdict_has_a_row():
    assert set(STATUS_BY_VERDICT) == {v.value for v in Verdict}, "a new Verdict must get a status row"


def test_every_row_maps_to_a_real_status():
    assert all(isinstance(s, Status) for s in STATUS_BY_VERDICT.values())


def test_an_empty_verdict_is_unmapped(tmp_path):
    s = Session(session_id="e", problem=Problem(slug="p", title="P", difficulty="Easy", tags=[], description=None),
                snapshots=[Snapshot(ts=datetime(2026, 11, 1, tzinfo=UTC), code="", language="python3")],
                events=[SubmitEvent(ts=datetime(2026, 11, 1, 0, 5, tzinfo=UTC), verdict="", tests_passed=None,
                                    tests_total=None, error_detail=None, source="capture_submit")],
                submit_capture_reliable=True)
    settings = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path)}, dotenv_path=tmp_path / "none.env")
    assert status(s, settings=settings, run_id="r").status == Status.UNKNOWN
    assert "unmapped_verdict" in (tmp_path / "pipeline.jsonl").read_text()
