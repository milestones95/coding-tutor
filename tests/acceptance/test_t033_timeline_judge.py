"""Acceptance tests for T-033: the timeline judge, its scoring, and the agreement maths.
Tester-owned (`/test write T-033`, 2026-11-08). Interfaces (D-062):

    evals.graders.timeline_judge.TimelineJudge   name "timeline-judge", version "v1", kind "llm_judge",
        field "timeline_judge"; grade(case, output, ctx) needs ctx.client and ctx.session.
        Grades: timeline_checklist (share of applicable items met) first, then checklist.<item>.
        Five items judged by the model; at_most_5_sentences counted by code; no_invented_correction
        left out when the account says the person switched approach (corrected).
    evals.calibrate.agreement.agreement(human, judge) -> {agreement, n, always_yes, misses_caught}
    runner wiring (builder, D-062): graders_for("timeline") → [TimelineJudge()], and run() gives every
    grader GradeContext(client=…, session=<the case's Session>).
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
T0 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
ITEMS = ["approaches", "first_approach", "no_invented_correction", "final_and_outcome", "no_invented_events"]


def _expected(corrected=None, on_track=True):
    return {"checklist": {"approaches": ["APPROACH-ONE", "APPROACH-TWO"],
                          "course_correction": {"first_approach_on_track": on_track, "corrected": corrected,
                                                "at_min": 9 if corrected else None},
                          "final_approach": "FINAL-APPROACH", "outcome": "Wrong Answer, 3/9 tests passed"},
            "key_facts": ["KEY-FACT"]}


def _answer(**met):
    return {i: {"reason": "because", "met": met.get(i, True)} for i in ITEMS}


def _session():
    from tutor.models import Problem, RunEvent, Session, Snapshot

    return Session(session_id="t033", problem=Problem(slug="probe", title="Probe", difficulty="Easy", tags=[],
                                                      description=None),
                   snapshots=[Snapshot(ts=T0, code="x = 1\n", language="python3")],
                   events=[RunEvent(ts=T0 + timedelta(minutes=2), status="Wrong Answer (sample tests)", tests_passed=1,
                                    tests_total=3, error_detail="RUN-ERROR-TEXT")],
                   submit_capture_reliable=True)


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def _grade(settings, answer, expected, summary="One. Two. Three."):
    from evals.graders.base import GradeContext
    from evals.graders.timeline_judge import TimelineJudge
    from tutor.llm import LLMClient

    fake = FakeAdapter([answer])
    client = LLMClient(settings, adapters={"openai": fake}, sleep=lambda s: None)
    judge = TimelineJudge()
    grades = judge.grade(SimpleNamespace(expected=expected), {"summary": summary},
                         GradeContext(client=client, session=_session()))
    return {g.metric: g.value for g in grades}, [g.metric for g in grades], fake, judge


# ---------------------------------------------------------------- 1. the judge and its score


def test_all_items_met_scores_one(settings):
    g, order, _, judge = _grade(settings, _answer(), _expected())
    assert order[0] == "timeline_checklist" and g["timeline_checklist"] == 1.0
    assert {f"checklist.{i}" for i in ITEMS} | {"checklist.at_most_5_sentences"} == set(order[1:])
    assert (judge.name, judge.version, judge.kind, judge.field) == ("timeline-judge", "v1", "llm_judge", "timeline_judge")
    assert judge.last_usage is not None


def test_the_score_is_the_share_of_items_met_with_the_length_counted_by_code(settings):
    long = "A. B. C. D. E. F."
    g, _, _, _ = _grade(settings, _answer(first_approach=False), _expected(), summary=long)
    assert g["checklist.first_approach"] == 0.0 and g["checklist.at_most_5_sentences"] == 0.0
    assert g["timeline_checklist"] == pytest.approx(4 / 6)


def test_the_judge_cannot_overrule_the_sentence_count(settings):
    """The judge has no length item; even if it says everything is met, 6 sentences fail."""
    g, _, _, _ = _grade(settings, _answer(), _expected(), summary="A. B. C. D. E. F.")
    assert g["checklist.at_most_5_sentences"] == 0.0


def test_no_invented_correction_is_left_out_when_the_person_switched(settings):
    g, order, _, _ = _grade(settings, _answer(no_invented_correction=False), _expected(corrected=True, on_track=False))
    assert "checklist.no_invented_correction" not in order
    assert g["timeline_checklist"] == 1.0, "5 applicable items, all met"


def test_the_judge_reads_the_account_the_timeline_and_the_summary(settings):
    from tutor.condense import condense, render

    _, _, fake, _ = _grade(settings, _answer(), _expected(on_track=False, corrected=False), summary="SUMMARY-TEXT.")
    sent = "".join(m.content for m in fake.calls[0]["messages"])
    assert render(condense(_session())) in sent, "the one condenser's timeline (rule 3)"
    assert all(s in sent for s in ("APPROACH-ONE", "APPROACH-TWO", "FINAL-APPROACH", "3/9", "SUMMARY-TEXT."))
    assert "never switched" in sent


def test_the_judge_needs_the_session(settings):
    from evals.graders.base import GradeContext
    from evals.graders.timeline_judge import TimelineJudge

    with pytest.raises(ValueError):
        TimelineJudge().grade(SimpleNamespace(expected=_expected()), {"summary": "x."}, GradeContext(client=object()))


def test_the_judge_prompt_is_pinned_and_checks_every_item():
    from tutor.prompts import load_prompt

    p = load_prompt("judges/timeline", "v1")
    assert json.loads((REPO / "prompts" / "manifest.json").read_text()).get("judges/timeline/v1.md") == p.sha256
    text = (REPO / "prompts" / "judges" / "timeline" / "v1.md").read_text()
    assert all(i in text for i in ITEMS)
    assert "sentence" not in text.lower().replace("one-sentence reason", ""), "length is code's job, not the judge's"
    slugs = {json.loads(r)["problem"]["slug"] for r in (SYN / "specs.jsonl").read_text().splitlines() if r.strip()}
    assert not [s for s in slugs if s in text], "rule 9: no dataset problem named"


# ---------------------------------------------------------------- 2. grade the agreement maths


def test_agreement_is_item_by_item_and_skips_not_applicable():
    from evals.calibrate.agreement import agreement

    human = [{"a": True, "b": False, "c": None}, {"a": True, "b": True, "c": True}]
    judge = [{"a": True, "b": True, "c": False}, {"a": False, "b": True, "c": True}]
    r = agreement(human, judge)
    assert r["n"] == 5 and r["agreement"] == pytest.approx(3 / 5)
    assert r["always_yes"] == pytest.approx(4 / 5) and r["misses_caught"] == (0, 1)


def test_a_judge_that_always_says_yes_is_exposed():
    from evals.calibrate.agreement import agreement

    human = [{"a": True}] * 9 + [{"a": False}]
    r = agreement(human, [{"a": True}] * 10)
    assert r["agreement"] == pytest.approx(0.9) and r["always_yes"] == pytest.approx(0.9)
    assert r["misses_caught"] == (0, 1)


# ---------------------------------------------------------------- 3. runner wiring (builder)


def test_the_timeline_suite_is_graded_by_the_judge():
    from evals.graders.timeline_judge import TimelineJudge
    from tutor.evals.runner import graders_for

    gs = graders_for("timeline")
    assert isinstance(gs[0], TimelineJudge)


def test_the_runner_gives_graders_the_cases_session(settings, tmp_path):
    import shutil

    from tutor.evals.runner import run

    syn = tmp_path / "evals" / "data" / "sessions" / "synthetic"
    syn.mkdir(parents=True)
    for ext in (".json", ".meta.json"):
        shutil.copy(SYN / f"syn-004{ext}", syn / f"syn-004{ext}")
    f = tmp_path / "evals" / "data" / "timeline" / "dev" / "cases.jsonl"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps({"case_id": "timeline-dev-001", "suite": "timeline", "split": "dev",
                             "dataset_version": "dev-v1", "source": "synthetic",
                             "session": {"synthetic_path": "evals/data/sessions/synthetic/syn-004.json"},
                             "expected": _expected(), "label_source": "human_written"}) + "\n")
    seen = []

    class Spy:
        name, version, kind = "spy", "v1", "deterministic"

        def grade(self, case, output, ctx):
            from evals.graders.base import Grade

            seen.append(ctx.session.session_id if ctx and ctx.session else None)
            return [Grade(metric="spy", value=1.0)]

    class Echo:
        name, version = "echo", "t"

        def __call__(self, session):
            return {"summary": "x."}

    run("timeline", "dev", predictor=Echo(), settings=settings, root=tmp_path / "evals",
        results_dir=tmp_path / "results", graders=[Spy()])
    assert seen == ["syn-004"]
