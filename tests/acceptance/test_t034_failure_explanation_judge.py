"""Acceptance tests for T-034: the failure-explanation judge and its calibration set.
Tester-owned (`/test write T-034`, 2026-11-08). Interfaces (D-065):

    evals.graders.failure_explanation_judge.FailureExplanationJudge
        name "failure-explanation-judge", version "v2" (v1 rejected, D-067), kind "llm_judge", field "failure_explanation_judge";
        grade(case, output, ctx) needs ctx.client and ctx.session when there is an explanation, and
        returns no grades when there is none (a passed session, §6.3).
        Grades: explanation_checklist (share of the 2 items met) first, then explanation.<item>.
        Items: consistent, no_invented_cause (eval plan "consistent with the real failure, no invented causes").
    evals/data/calibration/failure_explanation/v1.jsonl: 20 explanations from stored M3 dev records,
        each graded by the human on both items.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from _llm_fake import FakeAdapter

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
SYN = REPO / "evals" / "data" / "sessions" / "synthetic"
CAL = REPO / "evals" / "data" / "calibration" / "failure_explanation" / "v1.jsonl"
T0 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
ITEMS = ["consistent", "no_invented_cause"]


def _expected():
    return {"failure_type": "edge_case_missed", "key_facts": ["KEY-FACT-ONE", "KEY-FACT-TWO"]}


def _answer(**met):
    return {i: {"reason": "because", "met": met.get(i, True)} for i in ITEMS}


def _session():
    from tutor.models import Problem, RunEvent, Session, Snapshot

    return Session(session_id="t034", problem=Problem(slug="probe", title="Probe", difficulty="Easy", tags=[],
                                                      description=None),
                   snapshots=[Snapshot(ts=T0, code="x = 1\n", language="python3")],
                   events=[RunEvent(ts=T0 + timedelta(minutes=2), status="Wrong Answer (sample tests)", tests_passed=1,
                                    tests_total=3, error_detail="RUN-ERROR-TEXT")],
                   submit_capture_reliable=True)


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def _grade(settings, answer, explanation="EXPLANATION-TEXT."):
    from evals.graders.base import GradeContext
    from evals.graders.failure_explanation_judge import FailureExplanationJudge
    from tutor.llm import LLMClient

    fake = FakeAdapter([answer])
    client = LLMClient(settings, adapters={"openai": fake}, sleep=lambda s: None)
    judge = FailureExplanationJudge()
    grades = judge.grade(SimpleNamespace(expected=_expected()),
                         {"failure_type": "edge_case_missed", "source": "llm", "explanation": explanation},
                         GradeContext(client=client, session=_session()))
    return {g.metric: g.value for g in grades}, [g.metric for g in grades], fake, judge


# ---------------------------------------------------------------- 1. the judge and its score


def test_both_items_met_scores_one(settings):
    g, order, _, judge = _grade(settings, _answer())
    assert order == ["explanation_checklist", "explanation.consistent", "explanation.no_invented_cause"]
    assert g["explanation_checklist"] == 1.0
    assert (judge.name, judge.version, judge.kind, judge.field) == (
        "failure-explanation-judge", "v2", "llm_judge", "failure_explanation_judge")   # v1 rejected at calibration (D-067)
    assert judge.last_usage is not None


@pytest.mark.parametrize(("miss", "want"), [({"consistent": False}, 0.5), ({"no_invented_cause": False}, 0.5),
                                            ({"consistent": False, "no_invented_cause": False}, 0.0)])
def test_the_score_is_the_share_of_items_met(settings, miss, want):
    g, _, _, _ = _grade(settings, _answer(**miss))
    assert g["explanation_checklist"] == pytest.approx(want)
    assert all(g[f"explanation.{i}"] == 0.0 for i in miss)


def test_the_judge_reads_the_account_the_timeline_and_the_explanation(settings):
    from tutor.condense import condense, render

    _, _, fake, _ = _grade(settings, _answer())
    sent = "".join(m.content for m in fake.calls[0]["messages"])
    assert render(condense(_session())) in sent, "the one condenser's timeline (rule 3)"
    assert all(s in sent for s in ("edge_case_missed", "KEY-FACT-ONE", "KEY-FACT-TWO", "EXPLANATION-TEXT."))


def test_a_passed_session_has_nothing_to_judge(settings):
    from evals.graders.base import GradeContext
    from evals.graders.failure_explanation_judge import FailureExplanationJudge

    fake = FakeAdapter([])
    j = FailureExplanationJudge()
    out = {"failure_type": "none", "source": "rule", "explanation": None}
    assert j.grade(SimpleNamespace(expected={"failure_type": "none", "key_facts": []}), out,
                   GradeContext(client=object(), session=_session())) == []
    assert fake.calls == [] and j.last_usage is None


def test_the_judge_needs_the_session(settings):
    from evals.graders.base import GradeContext
    from evals.graders.failure_explanation_judge import FailureExplanationJudge

    with pytest.raises(ValueError):
        FailureExplanationJudge().grade(SimpleNamespace(expected=_expected()), {"explanation": "x."},
                                        GradeContext(client=object()))


def test_the_judge_prompt_is_pinned_and_checks_both_items():
    from tutor.prompts import load_prompt

    p = load_prompt("judges/failure_explanation", "v2")
    assert json.loads((REPO / "prompts" / "manifest.json").read_text()).get("judges/failure_explanation/v2.md") == p.sha256
    text = (REPO / "prompts" / "judges" / "failure_explanation" / "v2.md").read_text()
    assert all(i in text for i in ITEMS)
    slugs = {json.loads(r)["problem"]["slug"] for r in (SYN / "specs.jsonl").read_text().splitlines() if r.strip()}
    assert not [s for s in slugs if s in text], "rule 9: no dataset problem named"


# ---------------------------------------------------------------- 2. the calibration set


def _cal():
    return [json.loads(x) for x in CAL.read_text().splitlines() if x.strip()]


def test_the_calibration_set_has_20_human_graded_dev_explanations():
    rows = _cal()
    assert len(rows) == 20 and len({r["item_id"] for r in rows}) == 20
    dev = {json.loads(x)["case_id"] for x in (REPO / "evals/data/failure/dev/cases.jsonl").read_text().splitlines()}
    assert all(r["case_id"] in dev for r in rows), "dev cases only (rule 2)"
    assert all(set(r["human"]) == set(ITEMS) and all(isinstance(v, bool) for v in r["human"].values()) for r in rows)
    assert all(r["graded_by"].startswith("human") for r in rows)


def test_each_explanation_is_one_the_field_really_produced():
    """Copied from a stored M3 dev record, byte for byte: the judge is calibrated on real outputs.
    Result records are gitignored, so a checkout without them skips this check."""
    for r in _cal():
        f = REPO / "evals/results/failure" / f"{r['source_run_id']}.json"
        if not f.exists():
            pytest.skip(f"result record {f.name} is not in this checkout")
        rec = json.loads(f.read_text())
        outs = [c["output"]["explanation"] for c in rec["cases"]
                if c["case_id"] == r["case_id"] and (c.get("output") or {}).get("explanation")]
        assert r["explanation"] in outs, r["item_id"]


def test_the_set_has_misses_to_catch():
    """A set where everything is met can't tell a judge from one that always says yes (D-063)."""
    misses = sum(v is False for r in _cal() for v in r["human"].values())
    assert misses >= 3


def test_the_calibration_script_knows_this_judge():
    src = (REPO / "evals/calibrate/calibrate_judge.py").read_text()
    assert "failure_explanation" in src and "FailureExplanationJudge" in src
