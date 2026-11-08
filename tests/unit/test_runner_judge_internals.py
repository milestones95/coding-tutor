"""Unit tests for the runner's judge internals (builder-owned, T-032)."""

import json


def test_a_malformed_calibration_file_reads_as_uncalibrated(tmp_path):
    from tutor.evals.runner import _is_calibrated

    p = tmp_path / "calibration.json"
    for text in ("not json", "[]", '{"entries": "x"}', '{"entries": [{"judge": "j", "version": "v1", "agreement": "0.9"}]}'):
        p.write_text(text)
        assert _is_calibrated("j", "v1", p) is False, text


def test_agreement_exactly_at_the_threshold_counts(tmp_path):
    from tutor.evals.runner import _is_calibrated

    p = tmp_path / "calibration.json"
    p.write_text(json.dumps({"entries": [{"judge": "j", "version": "v1", "agreement": 0.85, "n": 20, "decision": "a"}]}))
    assert _is_calibrated("j", "v1", p) is True
    assert _is_calibrated("j", "v2", p) is False


def test_by_metric_skips_rows_with_an_error():
    from tutor.evals.runner import _by_metric

    rows = [{"error": None, "grades": [{"metric": "a", "value": 1.0}, {"metric": "b", "value": 0.0}]},
            {"error": "judge: x", "grades": [{"metric": "a", "value": 0.0}]},
            {"error": None, "grades": [{"metric": "a", "value": 0.0}]}]
    assert _by_metric(rows) == {"a": {"mean": 0.5, "n": 2}, "b": {"mean": 0.0, "n": 1}}


def test_judge_label():
    from tutor.evals.runner import _judge_label

    assert _judge_label(None) == "—"
    assert _judge_label({"name": "j", "version": "v1", "calibrated": False}) == "j-v1 (uncalibrated)"
    assert _judge_label({"name": "j", "version": "v1", "calibrated": True}) == "j-v1"
