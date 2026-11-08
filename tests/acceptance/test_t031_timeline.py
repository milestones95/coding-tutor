"""Acceptance tests for T-031: the timeline summary field. Tester-owned (`/test write T-031`,
2026-11-08). Interfaces (D-060):

    tutor.fields.timeline
        PROMPT = "timeline"                                 # pinned in tutor.toml [prompts]
        class TimelineOutput(BaseModel): summary: str       # non-empty
        timeline(session, *, client, settings, run_id, model=None) -> LLMResult[TimelineOutput]
    Behaviour (eval plan "Timeline summary … 3–5 sentences"; architecture §6.3):
        one structured call; the input is render(condense(session)) unchanged (rule 3), so the
        verdict, runs and errors are in it. The prompt asks for 3–5 sentences; the field does not
        enforce the count: the `at_most_5_sentences` grader measures it, and enforcing it in the
        schema would hide the metric.
    runner: predictor_named("timeline", *, settings, client=None, model=None), output {"summary"},
        prompt_versions {"timeline": "v1"}; graders_for("timeline") → [SentenceCount] (the judge
        joins in T-033).
"""

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from _llm_fake import FakeAdapter

REPO = Path(__file__).resolve().parents[2]
SYN = REPO / "evals" / "data" / "sessions" / "synthetic"
T0 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
SUMMARY = ("You started with a hash map of values to indexes. The first run failed one sample test. "
           "You split the fill and the lookup into two loops. The submit was accepted.")


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def _client(settings, script):
    from tutor.llm import LLMClient

    fake = FakeAdapter(script)
    return LLMClient(settings, adapters={"openai": fake}, sleep=lambda s: None), fake


def _session():
    from tutor.models import Problem, RunEvent, Session, Snapshot, SubmitEvent

    return Session(
        session_id="t031-1",
        problem=Problem(slug="probe", title="Probe Problem", difficulty="Medium", tags=["array"], description=None),
        snapshots=[Snapshot(ts=T0, code="class Solution:\n    pass\n", language="python3"),
                   Snapshot(ts=T0 + timedelta(minutes=6), code="class Solution:\n    seen = {}\n", language="python3")],
        events=[RunEvent(ts=T0 + timedelta(minutes=3), status="Wrong Answer (sample tests)", tests_passed=1,
                         tests_total=3, error_detail="Output: [1]\nExpected: [2]"),
                SubmitEvent(ts=T0 + timedelta(minutes=8), verdict="Accepted", tests_passed=40, tests_total=40,
                            error_detail=None, source="capture_submit")],
        submit_capture_reliable=True)


def _sent(fake, i=0):
    return "".join(m.content for m in fake.calls[i]["messages"])


# ---------------------------------------------------------------- 1. one call on the one condenser


def test_one_call_returns_the_summary(settings):
    from tutor.fields.timeline import timeline

    client, fake = _client(settings, [{"summary": SUMMARY}])
    r = timeline(_session(), client=client, settings=settings, run_id="r")
    assert r.output.summary == SUMMARY and len(fake.calls) == 1
    assert r.usage.input_tokens == 1000


def test_the_input_is_the_one_condensers_render(settings):
    from tutor.condense import condense, render
    from tutor.fields.timeline import timeline

    s = _session()
    client, fake = _client(settings, [{"summary": SUMMARY}])
    timeline(s, client=client, settings=settings, run_id="r")
    assert render(condense(s)) in _sent(fake), "rule 3: the rendered condensed timeline, unchanged"


def test_an_empty_summary_is_invalid_and_retried(settings):
    from tutor.fields.timeline import timeline

    client, fake = _client(settings, [{"summary": ""}, {"summary": SUMMARY}])
    r = timeline(_session(), client=client, settings=settings, run_id="r")
    assert r.output.summary == SUMMARY and len(fake.calls) == 2


def test_the_call_is_logged_with_field_and_prompt_version(settings):
    from tutor.fields.timeline import timeline

    client, _ = _client(settings, [{"summary": SUMMARY}])
    timeline(_session(), client=client, settings=settings, run_id="r-log")
    row = json.loads((settings.paths.logs / "llm_calls.jsonl").read_text().splitlines()[-1])
    assert (row["field"], row["prompt_version"], row["run_id"]) == ("timeline", settings.prompts["timeline"], "r-log")


# ---------------------------------------------------------------- 2. the prompt file


def test_the_prompt_is_versioned_pinned_and_asks_for_the_checklist(settings):
    from tutor.prompts import load_prompt

    assert (settings.prompts.get("timeline") or "").startswith("v")   # a later version is pinned by T-036; v1 kept as written
    p = load_prompt("timeline", "v1")
    assert json.loads((REPO / "prompts" / "manifest.json").read_text()).get("timeline/v1.md") == p.sha256
    assert "timeline" in p.variables
    text = (REPO / "prompts" / "timeline" / "v1.md").read_text().lower()
    assert "3" in text and "5" in text and "sentence" in text, "the prompt states the 3–5 sentence length"
    assert "approach" in text and "outcome" in text
    slugs = {json.loads(r)["problem"]["slug"] for r in (SYN / "specs.jsonl").read_text().splitlines() if r.strip()}
    assert not [s for s in slugs if s in text], "rule 9: no dataset problem named"


# ---------------------------------------------------------------- 3. through the runner


def _row(n, sid):
    return {"case_id": f"timeline-dev-{n:03d}", "suite": "timeline", "split": "dev", "dataset_version": "dev-v1",
            "source": "synthetic", "session": {"synthetic_path": f"evals/data/sessions/synthetic/{sid}.json"},
            "expected": {"checklist": {"approaches": [f"APPROACH-SENTINEL-{n}"],
                                       "course_correction": {"first_approach_on_track": True, "corrected": None,
                                                             "at_min": None},
                                       "final_approach": f"FINAL-SENTINEL-{n}", "outcome": "Accepted, 1/1 tests passed"},
                         "key_facts": [f"KEYFACT-SENTINEL-{n}"]},
            "label_source": "human_written", "tags": [], "notes": "NOTES-SENTINEL"}


@pytest.fixture
def root(tmp_path):
    syn = tmp_path / "evals" / "data" / "sessions" / "synthetic"
    syn.mkdir(parents=True)
    for sid in ("syn-004", "syn-009"):
        for ext in (".json", ".meta.json"):
            shutil.copy(SYN / f"{sid}{ext}", syn / f"{sid}{ext}")
    f = tmp_path / "evals" / "data" / "timeline" / "dev" / "cases.jsonl"
    f.parent.mkdir(parents=True)
    f.write_text("".join(json.dumps(_row(n, sid)) + "\n" for n, sid in ((1, "syn-004"), (2, "syn-009"))))
    return tmp_path / "evals"


def test_the_runner_records_versions_cost_and_the_sentence_count(root, settings, tmp_path):
    from tutor.evals.runner import predictor_named, run, summary_line
    from tutor.prompts import load_prompt

    long = " ".join(f"Sentence number {i} happened." for i in range(1, 8))
    client, fake = _client(settings, [{"summary": SUMMARY}, {"summary": long}])
    pred = predictor_named("timeline", settings=settings, client=client)
    # T-033 made the calibrated judge the suite's default grader; this test is about the predictor's
    # record, so it names the code-counted grader explicitly (`/test write` correction, 2026-11-08)
    import sys
    sys.path.insert(0, str(REPO))
    from evals.graders.sentence_count import SentenceCount

    rec = run("timeline", "dev", predictor=pred, settings=settings, root=root, results_dir=tmp_path / "results",
              graders=[SentenceCount()])
    assert len(fake.calls) == 2
    pin = settings.prompts["timeline"]   # pinned version, not a literal: T-036 pins timeline v2 (`/test write` correction, 2026-11-08)
    assert rec["prompt_versions"] == {"timeline": pin}
    assert rec["prompt_sha256"] == {"timeline": load_prompt("timeline", pin).sha256}
    assert (rec["provider"], rec["model"], rec["metric"]) == ("openai", "gpt-5.5", "sentence_count")
    outs = {c["case_id"]: c for c in rec["cases"]}
    assert outs["timeline-dev-001"]["output"] == {"summary": SUMMARY}
    assert [g["value"] for g in outs["timeline-dev-001"]["grades"]] == [1.0]
    assert [g["value"] for g in outs["timeline-dev-002"]["grades"]] == [0.0], "7 sentences fails the checklist"
    assert rec["aggregates"]["accuracy"] == pytest.approx(0.5)
    assert rec["cost_usd_total"] > 0
    assert f"prompt timeline-{pin}" in summary_line(rec)

