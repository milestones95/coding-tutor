"""Unit tests for fields/failure.py rules and the runner's FailureRulesPredictor (builder-owned, T-025)."""

import json
from pathlib import Path

import pytest

SYN = Path(__file__).resolve().parents[2] / "evals" / "data" / "sessions" / "synthetic"


def _predictor(tmp_path):
    from tutor.config import load_settings
    from tutor.evals.runner import FailureRulesPredictor

    return FailureRulesPredictor(load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path)}, dotenv_path=tmp_path / "x"))


def _session(sid):
    from tutor.models import Session

    return Session.model_validate(json.loads((SYN / f"{sid}.json").read_text()))


def test_rules_cover_exactly_two_statuses():
    from tutor.fields.failure import RULES
    from tutor.models import Status

    assert set(RULES) == {Status.PASSED, Status.FAILED_TOO_SLOW}


def test_predictor_output_shape_for_a_tle(tmp_path):
    assert _predictor(tmp_path)(_session("syn-005")) == {"failure_type": "too_slow", "source": "rule", "explanation": None}


def test_predictor_raises_for_a_wrong_answer(tmp_path):
    with pytest.raises(LookupError, match="failed_wrong_answer"):
        _predictor(tmp_path)(_session("syn-009"))
