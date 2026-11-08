"""Acceptance tests for T-037: the failure suite is graded by the explanation judge, and a judge counts
as calibrated only with an accepted decision. Tester-owned (`/test write T-037`, 2026-11-08).

    graders_for("failure") → [FailureTypeExact(), FailureExplanationJudge()]  (type first: accuracy reads it)
    _is_calibrated: the latest calibration.json entry for that judge name + exact version must have
        agreement >= 0.85 and decision "accept" (D-063: a judge that catches none of the misses is rejected).
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

from _llm_fake import FakeAdapter

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
SYN = REPO / "evals" / "data" / "sessions" / "synthetic"
JUDGE_OK = {"consistent": {"reason": "r", "met": True}, "no_invented_cause": {"reason": "r", "met": False}}


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def _row(n, sid, ftype, tags=()):
    return {"case_id": f"failure-dev-{n:03d}", "suite": "failure", "split": "dev", "dataset_version": "dev-v2",
            "source": "synthetic", "session": {"synthetic_path": f"evals/data/sessions/synthetic/{sid}.json"},
            "expected": {"failure_type": ftype, "key_facts": [f"KEY-FACT-{n}"]},
            "label_source": "human_written", "tags": list(tags), "notes": ""}


@pytest.fixture
def root(tmp_path):
    syn = tmp_path / "evals" / "data" / "sessions" / "synthetic"
    syn.mkdir(parents=True)
    for sid in ("syn-004", "syn-009"):
        for ext in (".json", ".meta.json"):
            shutil.copy(SYN / f"{sid}{ext}", syn / f"{sid}{ext}")
    f = tmp_path / "evals" / "data" / "failure" / "dev" / "cases.jsonl"
    f.parent.mkdir(parents=True)
    rows = [_row(1, "syn-004", "none", tags=["rule_decided"]), _row(2, "syn-009", "edge_case_missed")]
    f.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return tmp_path / "evals"


class Echo:
    """A free predictor: the first session passed (no explanation), the second failed."""
    name, version = "echo", "t"

    def __call__(self, session):
        if session.session_id.endswith("004") or "004" in session.session_id:
            return {"failure_type": "none", "source": "rule", "explanation": None}
        return {"failure_type": "edge_case_missed", "source": "llm", "explanation": "EXPLANATION-TEXT."}


def _run(root, settings, tmp_path, script):
    from tutor.evals.runner import run
    from tutor.llm import LLMClient

    fake = FakeAdapter(script)
    client = LLMClient(settings, adapters={"openai": fake}, sleep=lambda s: None)
    rec = run("failure", "dev", predictor=Echo(), settings=settings, root=root, results_dir=tmp_path / "results",
              judge_client=client)
    return rec, fake


# ---------------------------------------------------------------- 1. the failure suite's graders


def test_the_failure_suite_runs_the_type_grader_then_the_explanation_judge():
    from evals.graders.failure_explanation_judge import FailureExplanationJudge
    from evals.graders.failure_type_exact import FailureTypeExact
    from tutor.evals.runner import graders_for

    gs = graders_for("failure")
    assert [type(g) for g in gs] == [FailureTypeExact, FailureExplanationJudge]


def test_only_the_explanation_is_judged_and_accuracy_stays_the_failure_type(root, settings, tmp_path):
    rec, fake = _run(root, settings, tmp_path, [JUDGE_OK])
    assert len(fake.calls) == 1, "the passed session has no explanation, so no judge call"
    grades = {c["case_id"]: {g["metric"]: g["value"] for g in c["grades"]} for c in rec["cases"]}
    assert grades["failure-dev-001"] == {"failure_type_exact": 1.0}
    assert grades["failure-dev-002"]["failure_type_exact"] == 1.0
    assert grades["failure-dev-002"]["explanation_checklist"] == pytest.approx(0.5)
    assert rec["aggregates"]["accuracy"] == pytest.approx(1.0), "accuracy reads the type, not the judge"
    assert rec["aggregates"]["by_metric"]["explanation_checklist"] == {"mean": 0.5, "n": 1}
    assert rec["judge"]["name"] == "failure-explanation-judge"
    by_case = {c["case_id"]: c["judge_cost_usd"] for c in rec["cases"]}
    assert by_case["failure-dev-001"] == 0.0 and by_case["failure-dev-002"] > 0


# ---------------------------------------------------------------- 2. calibrated needs an accepted decision


def _calibrated(tmp_path, entries, name="j", version="v1"):
    from tutor.evals.runner import _is_calibrated

    p = tmp_path / "calibration.json"
    p.write_text(json.dumps({"entries": entries}))
    return _is_calibrated(name, version, p)


def _e(agreement, decision, version="v1", name="j"):
    return {"judge": name, "version": version, "agreement": agreement, "n": 40, "decision": decision}


@pytest.mark.parametrize("entries,want", [
    ([_e(0.90, "accept")], True),
    ([_e(0.90, "reject: caught 0/4 misses")], False),     # agreement alone is not enough (D-063, D-067)
    ([_e(0.84, "accept")], False),                        # nor is a decision alone
    ([_e(0.90, "accept"), _e(0.90, "reject")], False),    # the latest entry for that version decides
    ([_e(0.90, "reject"), _e(0.95, "accept")], True),
    ([_e(0.95, "accept", version="v2")], False),          # another version's acceptance doesn't count
])
def test_calibrated_needs_the_latest_entry_accepted_at_085(tmp_path, entries, want):
    assert _calibrated(tmp_path, entries) is want


def test_the_committed_calibration_file_reads_as_the_human_decided():
    from tutor.evals.runner import _is_calibrated

    p = REPO / "evals" / "calibration.json"
    assert _is_calibrated("timeline-judge", "v1", p)
    assert _is_calibrated("failure-explanation-judge", "v2", p)
    assert not _is_calibrated("failure-explanation-judge", "v1", p), "rejected at 0.90 with 0/4 misses (D-067)"
