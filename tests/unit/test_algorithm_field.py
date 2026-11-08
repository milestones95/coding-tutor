"""Unit tests for fields/algorithm.py and the runner's AlgorithmPredictor (builder-owned, T-024)."""

from datetime import UTC, datetime, timedelta

from _llm_fake import FakeAdapter

T0 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)


def _session(tags):
    from tutor.models import Problem, Session, Snapshot

    return Session(session_id="u1", problem=Problem(slug="p", title="P", difficulty="Hard", tags=tags, description=None),
                   snapshots=[Snapshot(ts=T0, code="first", language="python3"),
                              Snapshot(ts=T0 + timedelta(minutes=1), code="last", language="python3")],
                   events=[], submit_capture_reliable=True)


def test_variables_join_tags_and_use_the_last_snapshot():
    from tutor.fields.algorithm import variables

    v = variables(_session(["array", "graph"]))
    assert v == {"problem_title": "P", "difficulty": "Hard", "tags": "array, graph", "final_code": "last"}


def test_no_tags_reads_as_none():
    from tutor.fields.algorithm import variables

    assert variables(_session([]))["tags"] == "(none)"


def _predictor(tmp_path, script):
    from tutor.config import load_settings
    from tutor.evals.runner import AlgorithmPredictor
    from tutor.llm import LLMClient

    settings = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path)}, dotenv_path=tmp_path / "none.env")
    return AlgorithmPredictor(settings, client=LLMClient(settings, adapters={"openai": FakeAdapter(script)}))


def test_predictor_maps_labels_and_keeps_usage(tmp_path):
    p = _predictor(tmp_path, [{"algorithms": ["heap", "hash_map"]}])
    assert p(_session([])) == {"labels": ["heap", "hash_map"]}
    assert p.last_usage is not None and p.last_usage.input_tokens == 1000


def test_predictor_clears_usage_when_a_call_fails(tmp_path):
    import pytest

    from tutor.llm import LLMProviderError

    p = _predictor(tmp_path, [{"algorithms": ["heap"]}, LLMProviderError("x", retryable=False)])
    p(_session([]))
    with pytest.raises(LLMProviderError):
        p(_session([]))
    assert p.last_usage is None


def test_estimate_prices_a_call(tmp_path):
    p = _predictor(tmp_path, [])
    assert p.est_cost_per_call == (2000 * 5.0 + 500 * 30.0) / 1_000_000
