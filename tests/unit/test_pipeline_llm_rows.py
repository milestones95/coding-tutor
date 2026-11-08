"""Unit tests for the pipeline's LLM row builder (builder-owned, T-027; the timeline field T-031).

Call order per session: failure (unless decided with no call), timeline, algorithm."""

from datetime import UTC, datetime

from _llm_fake import FakeAdapter

T0 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)


def _session(verdict):
    from tutor.models import Problem, Session, Snapshot, SubmitEvent

    return Session(session_id=f"u-{verdict}", problem=Problem(slug="p", title="P", difficulty="Easy", tags=[],
                                                              description=None),
                   snapshots=[Snapshot(ts=T0, code="x", language="python3")],
                   events=[SubmitEvent(ts=T0, verdict=verdict, tests_passed=1, tests_total=2, error_detail=None,
                                       source="capture_submit")], submit_capture_reliable=True)


def _rows(tmp_path, script, sessions):
    from tutor.analyzer.pipeline import _llm_rows
    from tutor.config import load_settings
    from tutor.llm import LLMClient

    settings = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path)}, dotenv_path=tmp_path / "x")
    client = LLMClient(settings, adapters={"openai": FakeAdapter(script)})
    return _llm_rows(sessions, {s.session_id: "c1" for s in sessions}, settings, run_id="r", client=client,
                     model=None, now="now", log=tmp_path / "p.jsonl")


def test_a_passed_session_makes_no_failure_call_or_provenance_row(tmp_path):
    rows = _rows(tmp_path, [{"summary": "S."}, {"algorithms": ["stack"]}], [_session("Accepted")])
    assert rows.analysis == [("u-Accepted", "none", "rule", None, "S.", "c1", "now")]
    assert [p[1] for p in rows.provenance] == ["timeline_summary", "algorithm"]
    assert [p[2] for p in rows.provenance] == ["timeline", "algorithm"], "prompt_name stays the prompt's name"
    assert rows.algorithms == [("u-Accepted", "stack")]


def test_duplicate_labels_become_one_row(tmp_path):
    rows = _rows(tmp_path, [{"summary": "S."}, {"algorithms": ["stack", "stack"]}], [_session("Accepted")])
    assert rows.algorithms == [("u-Accepted", "stack")]


def test_every_field_failing_counts_three_errors(tmp_path):
    from tutor.llm import LLMProviderError

    boom = LLMProviderError("x", retryable=False)
    rows = _rows(tmp_path, [boom, boom, boom], [_session("Wrong Answer")])
    assert rows.errors == 3 and rows.provenance == [] and rows.algorithms == []
    assert rows.analysis == [("u-Wrong Answer", None, None, None, None, "c1", "now")]


def test_only_the_timeline_failing_keeps_the_other_fields(tmp_path):
    from tutor.llm import LLMProviderError

    script = [{"failure_type": "implementation_bug", "explanation": "Off by one."},
              LLMProviderError("x", retryable=False), {"algorithms": ["stack"]}]
    rows = _rows(tmp_path, script, [_session("Wrong Answer")])
    assert rows.errors == 1 and [p[1] for p in rows.provenance] == ["failure", "algorithm"]
    assert rows.analysis == [("u-Wrong Answer", "implementation_bug", "llm", "Off by one.", None, "c1", "now")]
