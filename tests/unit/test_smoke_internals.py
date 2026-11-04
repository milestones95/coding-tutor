"""Builder unit tests for tutor.smoke (T-007). FakeAdapter, tiny capture DB, no network."""

import pytest

from _capture_fixture import PROBLEM, build
from _llm_fake import FakeAdapter
from tutor.config import load_settings
from tutor.llm import LLMClient, LLMConfigError
from tutor.smoke import run_smoke


@pytest.fixture
def settings(tmp_path):
    db = build(tmp_path / "frozen.db", sessions=[{"id": "s", "started_at": "2026-11-01T10:00:00.000Z"}],
               snapshots=[{"session_id": "s", "ts": f"2026-11-01T10:0{i}:00.000Z", "code": str(i)} for i in range(2)])
    return load_settings(env={"TUTOR__PATHS__EVAL_CAPTURE_DB": str(db),
                              "TUTOR__PATHS__VERDICTS": str(tmp_path / "none.csv"),
                              "TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def test_run_smoke_sends_the_title_and_returns_the_validated_output(settings):
    fake = FakeAdapter([{"problem_slug": "probe-problem"}])
    ref, r = run_smoke(settings, "s", client=LLMClient(settings, adapters={"openai": fake}))
    assert str(ref) == "openai:gpt-5.5" and r.output.problem_slug == "probe-problem"
    assert PROBLEM["title"] in fake.calls[0]["messages"][0].content


def test_the_model_flag_is_used_and_reported(settings):
    fake = FakeAdapter([{"problem_slug": "x"}])
    ref, _ = run_smoke(settings, "s", model="openai:gpt-5.5", client=LLMClient(settings, adapters={"openai": fake}))
    assert str(ref) == "openai:gpt-5.5" and fake.calls[0]["model"] == "gpt-5.5"


def test_a_bad_model_fails_before_the_session_is_loaded(settings):
    # "missing" isn't a session: if the model were checked after loading, this would be a LookupError.
    with pytest.raises(LLMConfigError):
        run_smoke(settings, "missing", model="not-a-ref")
