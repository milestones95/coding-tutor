"""Acceptance tests for T-025: failure-type rules, the exact-match grader, and the rule/LLM split.
Tester-owned (`/test write T-025`, 2026-11-07). Interfaces (D-055):

    tutor.models.FailureType      StrEnum, values = the §3.2 CHECK list
    tutor.fields.failure.failure_rule(status: Status) -> FailureType | None
        passed → none; failed_too_slow → too_slow; anything else → None (the LLM decides)
    evals.graders.failure_type_exact.FailureTypeExact     (tester-owned)
    runner: graders_for("failure") → [FailureTypeExact]; predictor_named("failure_rules")
        → name "failure_rules", version "rules-v1", output {"failure_type", "source": "rule",
          "explanation": None}; it raises for a session the rules don't decide, which the
          runner scores as an error.
    record["aggregates"]["by_decider"] = {"rule": {"accuracy", "n"}, "llm": {"accuracy", "n"}}
        for the failure suite. The decider comes from the CASE (tag "rule_decided"), not from
        the output, so an LLM that wrongly claims "rule" can't move its own number.
        summary_line shows "rule X (n=..), llm Y (n=..)".
"""

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
SYN = REPO / "evals" / "data" / "sessions" / "synthetic"
sys.path.insert(0, str(REPO))


# ---------------------------------------------------------------- 1. FailureType


def test_failure_type_values_equal_the_schema_check_list():
    from tutor.models import FailureType

    assert {f.value for f in FailureType} == {"edge_case_missed", "wrong_approach", "too_slow",
                                             "implementation_bug", "did_not_finish", "none"}


# ---------------------------------------------------------------- 2. the rules


@pytest.mark.parametrize("status,expected", [
    ("passed", "none"), ("failed_too_slow", "too_slow"),
    ("failed_wrong_answer", None), ("failed_runtime_error", None), ("failed_output_limit", None),
    ("not_submitted", None), ("unknown", None),
])
def test_only_passed_and_too_slow_are_decided_by_rule(status, expected):
    from tutor.fields.failure import failure_rule
    from tutor.models import Status

    got = failure_rule(Status(status))
    assert (got.value if got is not None else None) == expected


# ---------------------------------------------------------------- 3. the grader


def _case(ft):
    return SimpleNamespace(expected={"failure_type": ft})


@pytest.mark.parametrize("output,expected,value", [
    ({"failure_type": "too_slow"}, "too_slow", 1.0),
    ({"failure_type": "edge_case_missed"}, "implementation_bug", 0.0),
    ({"failure_type": None}, "none", 0.0),
    ({}, "none", 0.0),
    ({"failure_type": "none", "explanation": "anything at all"}, "none", 1.0),   # explanation not graded here
])
def test_failure_type_exact(output, expected, value):
    from evals.graders.failure_type_exact import FailureTypeExact

    [g] = FailureTypeExact().grade(_case(expected), output, None)
    assert g.metric == "failure_type_exact" and g.value == value


# ---------------------------------------------------------------- 4. through the runner


def _row(n, sid, ft, tags):
    return {"case_id": f"failure-dev-{n:03d}", "suite": "failure", "split": "dev", "dataset_version": "dev-v1",
            "source": "synthetic", "session": {"synthetic_path": f"evals/data/sessions/synthetic/{sid}.json"},
            "expected": {"failure_type": ft, "key_facts": []}, "label_source": "human_written",
            "tags": tags, "notes": ""}


@pytest.fixture
def root(tmp_path):
    """syn-004 Accepted, syn-005 TLE (both rule-decided), syn-009 Wrong Answer (LLM-decided)."""
    syn = tmp_path / "evals" / "data" / "sessions" / "synthetic"
    syn.mkdir(parents=True)
    for sid in ("syn-004", "syn-005", "syn-009"):
        for ext in (".json", ".meta.json"):
            shutil.copy(SYN / f"{sid}{ext}", syn / f"{sid}{ext}")
    f = tmp_path / "evals" / "data" / "failure" / "dev" / "cases.jsonl"
    f.parent.mkdir(parents=True)
    rows = [_row(1, "syn-004", "none", ["rule_decided"]), _row(2, "syn-005", "too_slow", ["rule_decided"]),
            _row(3, "syn-009", "edge_case_missed", [])]
    f.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return tmp_path / "evals"


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def test_the_rules_predictor_scores_rule_cases_and_errors_the_rest(root, settings, tmp_path):
    from tutor.evals.runner import predictor_named, run, summary_line

    pred = predictor_named("failure_rules", settings=settings)
    assert (pred.name, pred.version) == ("failure_rules", "rules-v1")
    rec = run("failure", "dev", predictor=pred, settings=settings, root=root, results_dir=tmp_path / "results")
    agg = rec["aggregates"]
    assert agg["by_decider"]["rule"] == {"accuracy": 1.0, "n": 2}
    assert agg["by_decider"]["llm"] == {"accuracy": 0.0, "n": 1}
    assert agg["errors"] == 1 and agg["accuracy"] == pytest.approx(2 / 3)
    outs = {c["case_id"]: c["output"] for c in rec["cases"]}
    assert outs["failure-dev-001"] == {"failure_type": "none", "source": "rule", "explanation": None}
    assert outs["failure-dev-002"]["failure_type"] == "too_slow"
    line = summary_line(rec)
    assert "rule 1.00 (n=2)" in line and "llm 0.00 (n=1)" in line


class Claims:
    """An output that claims every case was rule-decided, and answers each one correctly."""
    name, version = "claims", "t-1"

    def __call__(self, session):
        ft = {"syn-004": "none", "syn-005": "too_slow", "syn-009": "edge_case_missed"}[session.session_id]
        return {"failure_type": ft, "source": "rule", "explanation": None}


def test_the_decider_split_comes_from_the_case_not_the_output(root, settings, tmp_path):
    from tutor.evals.runner import run

    rec = run("failure", "dev", predictor=Claims(), settings=settings, root=root, results_dir=tmp_path / "results")
    assert rec["aggregates"]["by_decider"]["rule"]["n"] == 2
    assert rec["aggregates"]["by_decider"]["llm"] == {"accuracy": 1.0, "n": 1}


def test_the_algorithm_suite_has_no_decider_split(tmp_path, settings):
    from tutor.evals.runner import run

    syn = tmp_path / "evals" / "data" / "sessions" / "synthetic"
    syn.mkdir(parents=True)
    for ext in (".json", ".meta.json"):
        shutil.copy(SYN / f"syn-005{ext}", syn / f"syn-005{ext}")
    f = tmp_path / "evals" / "data" / "algorithm" / "dev" / "cases.jsonl"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps({**_row(1, "syn-005", None, []), "suite": "algorithm", "case_id": "algorithm-dev-001",
                             "expected": {"labels": ["stack"]}}) + "\n")

    class Stack:
        name, version = "s", "t"

        def __call__(self, session):
            return {"labels": ["stack"]}

    rec = run("algorithm", "dev", predictor=Stack(), settings=settings, root=tmp_path / "evals",
              results_dir=tmp_path / "results")
    assert "by_decider" not in rec["aggregates"]
