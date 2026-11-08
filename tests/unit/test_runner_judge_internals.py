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


def test_a_case_that_fails_to_load_is_an_error_and_is_not_graded(tmp_path):
    import json as _json

    from tutor.config import load_settings
    from tutor.evals.runner import run

    f = tmp_path / "evals" / "data" / "timeline" / "dev" / "cases.jsonl"
    f.parent.mkdir(parents=True)
    f.write_text(_json.dumps({"case_id": "timeline-dev-001", "suite": "timeline", "split": "dev",
                              "dataset_version": "dev-v2", "source": "synthetic",
                              "session": {"synthetic_path": "evals/data/sessions/synthetic/missing.json"},
                              "expected": {}, "label_source": "human_written"}) + "\n")
    calls = []

    class G:
        name, version, kind = "g", "v1", "deterministic"

        def grade(self, case, output, ctx):
            calls.append(ctx)
            return []

    class P:
        name, version = "p", "t"

        def __call__(self, session):
            return {}

    settings = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "x")
    rec = run("timeline", "dev", predictor=P(), settings=settings, root=tmp_path / "evals",
              results_dir=tmp_path / "r", graders=[G()])
    assert calls == [] and rec["cases"][0]["error"].startswith("CaseError")
