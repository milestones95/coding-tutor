"""Acceptance tests for T-031: `tutor analyze --llm` writes the timeline summary (architecture §3.2;
D-057, D-060). Tester-owned (`/test write T-031`, 2026-11-08).

    With --llm, every session gets session_analysis.timeline_summary from fields/timeline.timeline
    (the same function the runner calls) and a field_provenance row with field 'timeline_summary',
    prompt_name 'timeline'. A timeline error is logged as `llm_field_failed` with field
    'timeline_summary', leaves the column NULL with no provenance row, and the other fields land.
"""

import json

import pytest

from test_t027_pipeline_llm import A, B, D, Router, _run, env, q  # noqa: F401  (fixture reuse)

SUMMARY = "You tried one idea. It ended as the verdict says."


class FailTimelineFor(Router):
    def __init__(self, marker):
        super().__init__()
        self.marker = marker

    def structured(self, **kw):
        from tutor.llm import LLMProviderError

        text = "".join(m.content for m in kw["messages"])
        if self.marker in text and "summary" in json.dumps(kw["schema"]):
            self.calls.append(kw)
            raise LLMProviderError("timeline provider down", retryable=False)
        return super().structured(**kw)


def test_every_session_gets_a_timeline_summary_and_provenance(env):
    report = _run(env, Router(), run_id="run-tl")
    assert report.llm_errors == 0
    rows = {r["session_id"]: r["timeline_summary"] for r in q(env, "SELECT * FROM session_analysis")}
    assert rows == {A: SUMMARY, B: SUMMARY, D: SUMMARY}
    prov = q(env, "SELECT * FROM field_provenance WHERE field = 'timeline_summary'")
    assert {p["session_id"] for p in prov} == {A, B, D}
    assert all((p["prompt_name"], p["prompt_version"], p["run_id"]) == ("timeline", "v1", "run-tl") for p in prov)


def test_the_timeline_reads_the_rendered_condensed_timeline(env):
    fake = Router()
    _run(env, fake)
    timeline_calls = [c for c in fake.calls if "summary" in json.dumps(c["schema"])]
    assert len(timeline_calls) == 3
    sent = ["".join(m.content for m in c["messages"]) for c in timeline_calls]
    assert all("Session:" in s and "FINAL CODE" in s for s in sent), "the condenser's render, not raw events"


def test_a_timeline_error_leaves_only_that_field_null(env):
    report = _run(env, FailTimelineFor("d = 1"))
    assert report.llm_errors == 1
    d = q(env, "SELECT * FROM session_analysis WHERE session_id = ?", D)[0]
    assert d["timeline_summary"] is None and d["failure_type"] == "implementation_bug"
    assert not q(env, "SELECT * FROM field_provenance WHERE session_id = ? AND field = 'timeline_summary'", D)
    events = [json.loads(x) for x in (env / "logs" / "pipeline.jsonl").read_text().splitlines()]
    failed = [e for e in events if e.get("event") == "llm_field_failed"]
    assert len(failed) == 1 and (failed[0]["session_id"], failed[0]["field"]) == (D, "timeline_summary")


def test_without_llm_no_timeline_summary_is_written(env):
    from tutor.analyzer.pipeline import analyze
    from tutor.config import load_settings

    analyze(load_settings(), run_id="r")
    assert q(env, "SELECT timeline_summary FROM session_analysis") == []


@pytest.mark.parametrize("field", ["timeline_summary"])
def test_the_schema_already_allows_the_field(env, field):
    """No migration: 0001 has the column and the provenance CHECK value (architecture §3.2)."""
    cols = {r["name"] for r in q(env, "PRAGMA table_info(session_analysis)")}
    assert field in cols
