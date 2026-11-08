"""Unit tests for fields/timeline.py and the runner's TimelinePredictor (builder-owned, T-031)."""

from datetime import UTC, datetime, timedelta

import pytest

from _llm_fake import FakeAdapter

T0 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)


def _session():
    from tutor.models import Problem, Session, Snapshot

    return Session(session_id="u1", problem=Problem(slug="p", title="P", difficulty="Hard", tags=["x"], description=None),
                   snapshots=[Snapshot(ts=T0, code="first", language="python3"),
                              Snapshot(ts=T0 + timedelta(minutes=1), code="last", language="python3")],
                   events=[], submit_capture_reliable=True)


def test_variables_are_title_difficulty_and_the_rendered_timeline():
    from tutor.condense import condense, render
    from tutor.fields.timeline import variables

    s = _session()
    assert variables(s) == {"problem_title": "P", "difficulty": "Hard", "timeline": render(condense(s))}


def test_a_whitespace_summary_is_rejected():
    from pydantic import ValidationError

    from tutor.fields.timeline import TimelineOutput

    with pytest.raises(ValidationError):
        TimelineOutput(summary="   ")


def _predictor(tmp_path, script):
    from tutor.config import load_settings
    from tutor.evals.runner import TimelinePredictor
    from tutor.llm import LLMClient

    settings = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path)}, dotenv_path=tmp_path / "none.env")
    return TimelinePredictor(settings, client=LLMClient(settings, adapters={"openai": FakeAdapter(script)}))


def test_predictor_returns_the_summary_and_keeps_usage(tmp_path):
    p = _predictor(tmp_path, [{"summary": "One. Two. Three."}])
    assert p(_session()) == {"summary": "One. Two. Three."}
    assert p.last_usage is not None and p.last_usage.output_tokens == 500


def test_predictor_clears_usage_when_a_call_fails(tmp_path):
    from tutor.llm import LLMProviderError

    p = _predictor(tmp_path, [{"summary": "One."}, LLMProviderError("x", retryable=False)])
    p(_session())
    with pytest.raises(LLMProviderError):
        p(_session())
    assert p.last_usage is None


def test_estimate_prices_a_call(tmp_path):
    p = _predictor(tmp_path, [])
    assert p.est_cost_per_call == pytest.approx((3000 * 5.0 + 250 * 30.0) / 1_000_000)
