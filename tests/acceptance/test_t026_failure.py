"""Acceptance tests for T-026: the failure field's LLM part. Tester-owned (`/test write T-026`,
2026-11-07). Interfaces (D-056):

    tutor.fields.failure
        PROMPT = "failure"                               # pinned in tutor.toml [prompts]
        class FailureOutput(BaseModel): failure_type: FailureType; source: "rule" | "llm";
                                        explanation: str | None
        class FailureResult(BaseModel): output: FailureOutput; usage: Usage | None
        failure(session, *, client, settings, run_id, model=None) -> FailureResult
    Behaviour (eval plan; architecture §6.3):
        passed           → none / rule / explanation None, and NO call
        failed_too_slow  → too_slow / rule; one call, for the explanation only (the model's type
                           is ignored)
        anything else    → one call; type and explanation from the model, source "llm"
        The model may never answer "none" (only Accepted is none); that answer is invalid and
        retried. not_submitted / unknown: the prompt says the outcome wasn't submitted / is unknown.
        Input: render(condense(session)) (rule 3: the one condenser) plus the verdict, test
        counts and error text.
    runner: predictor_named("failure", *, settings, client=None, model=None), output
        {"failure_type", "source", "explanation"}, prompt_versions {"failure": "v1"}, .last_usage
        (None when no call was made).
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
TYPES = ["edge_case_missed", "wrong_approach", "too_slow", "implementation_bug", "did_not_finish"]


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def _client(settings, script):
    from tutor.llm import LLMClient

    fake = FakeAdapter(script)
    return LLMClient(settings, adapters={"openai": fake}, sleep=lambda s: None), fake


def _session(*, verdict=None, reliable=True, passed=None, total=None, error=None):
    from tutor.models import Problem, RunEvent, Session, Snapshot, SubmitEvent

    events = [RunEvent(ts=T0 + timedelta(minutes=3), status="Wrong Answer (sample tests)", tests_passed=1,
                       tests_total=3, error_detail="Output: [1]\nExpected: [2]")]
    if verdict:
        events.append(SubmitEvent(ts=T0 + timedelta(minutes=8), verdict=verdict, tests_passed=passed,
                                  tests_total=total, error_detail=error, source="capture_submit"))
    return Session(session_id="t026-1",
                   problem=Problem(slug="probe", title="Probe Problem", difficulty="Medium", tags=["array"],
                                   description=None),
                   snapshots=[Snapshot(ts=T0, code="class Solution:\n    pass\n", language="python3"),
                              Snapshot(ts=T0 + timedelta(minutes=6), code="class Solution:\n    x = 1\n",
                                       language="python3")],
                   events=events, submit_capture_reliable=reliable)


def _sent(fake, i=0):
    return "".join(m.content for m in fake.calls[i]["messages"])


def _ans(t, why="It fails because of one thing."):
    return {"failure_type": t, "explanation": why}


# ---------------------------------------------------------------- 1. rules first, then one call


def test_passed_is_none_by_rule_with_no_call_and_no_explanation(settings):
    from tutor.fields.failure import failure

    client, fake = _client(settings, [])
    r = failure(_session(verdict="Accepted", passed=3, total=3), client=client, settings=settings, run_id="r")
    assert (r.output.failure_type.value, r.output.source, r.output.explanation) == ("none", "rule", None)
    assert fake.calls == [] and r.usage is None


def test_too_slow_keeps_the_rule_type_and_takes_only_the_explanation(settings):
    from tutor.fields.failure import failure

    client, fake = _client(settings, [_ans("implementation_bug", "Nested loops over the input time out.")])
    r = failure(_session(verdict="Time Limit Exceeded", passed=40, total=60), client=client, settings=settings, run_id="r")
    assert (r.output.failure_type.value, r.output.source) == ("too_slow", "rule")
    assert r.output.explanation == "Nested loops over the input time out."
    assert len(fake.calls) == 1 and r.usage is not None


def test_a_wrong_answer_is_decided_by_the_model(settings):
    from tutor.fields.failure import failure

    client, fake = _client(settings, [_ans("edge_case_missed", "Empty input returns the wrong value.")])
    r = failure(_session(verdict="Wrong Answer", passed=50, total=52), client=client, settings=settings, run_id="r")
    assert (r.output.failure_type.value, r.output.source) == ("edge_case_missed", "llm")
    assert r.output.explanation == "Empty input returns the wrong value."
    assert r.usage.input_tokens == 1000


@pytest.mark.parametrize("verdict,reliable", [("Wrong Answer", True), (None, True), (None, False)])
def test_the_model_may_not_answer_none(settings, verdict, reliable):
    from tutor.fields.failure import failure

    client, fake = _client(settings, [_ans("none"), _ans("did_not_finish")])
    r = failure(_session(verdict=verdict, reliable=reliable, passed=1, total=5), client=client, settings=settings,
                run_id="r")
    assert r.output.failure_type.value == "did_not_finish" and len(fake.calls) == 2


def test_not_submitted_and_unknown_say_so_in_the_prompt(settings):
    from tutor.fields.failure import failure

    client, fake = _client(settings, [_ans("did_not_finish"), _ans("did_not_finish")])
    failure(_session(reliable=True), client=client, settings=settings, run_id="r")
    failure(_session(reliable=False), client=client, settings=settings, run_id="r")
    assert "not submitted" in _sent(fake, 0).lower()
    assert "unknown" in _sent(fake, 1).lower()


# ---------------------------------------------------------------- 2. the input


def test_the_input_is_the_one_condensers_render_plus_verdict_counts_and_error(settings):
    from tutor.condense import condense, render
    from tutor.fields.failure import failure

    s = _session(verdict="Runtime Error", passed=12, total=40, error="IndexError: list index out of range")
    client, fake = _client(settings, [_ans("implementation_bug")])
    failure(s, client=client, settings=settings, run_id="r")
    text = _sent(fake)
    assert render(condense(s)) in text, "rule 3: the rendered condensed timeline, unchanged"
    assert "Runtime Error" in text and "12" in text and "40" in text and "IndexError" in text


def test_the_call_is_logged_with_field_and_prompt_version(settings):
    from tutor.fields.failure import failure

    client, _ = _client(settings, [_ans("wrong_approach")])
    failure(_session(verdict="Wrong Answer", passed=1, total=9), client=client, settings=settings, run_id="r-log")
    row = json.loads((settings.paths.logs / "llm_calls.jsonl").read_text().splitlines()[-1])
    assert (row["field"], row["prompt_version"], row["run_id"]) == ("failure", "v1", "r-log")


# ---------------------------------------------------------------- 3. the prompt file


def test_the_prompt_is_versioned_pinned_and_offers_every_non_none_type(settings):
    from tutor.prompts import load_prompt

    assert settings.prompts.get("failure") == "v1"
    p = load_prompt("failure", "v1")
    assert json.loads((REPO / "prompts" / "manifest.json").read_text()).get("failure/v1.md") == p.sha256
    assert "timeline" in p.variables
    text = (REPO / "prompts" / "failure" / "v1.md").read_text()
    assert all(t in text for t in TYPES), "the prompt must offer every type the model may choose"
    slugs = {json.loads(r)["problem"]["slug"] for r in (SYN / "specs.jsonl").read_text().splitlines() if r.strip()}
    assert not [s for s in slugs if s in text], "rule 9: no dataset problem named"


# ---------------------------------------------------------------- 4. through the runner


def _row(n, sid, ft, tags, key_facts):
    return {"case_id": f"failure-dev-{n:03d}", "suite": "failure", "split": "dev", "dataset_version": "dev-v1",
            "source": "synthetic", "session": {"synthetic_path": f"evals/data/sessions/synthetic/{sid}.json"},
            "expected": {"failure_type": ft, "key_facts": key_facts}, "label_source": "human_written",
            "tags": tags, "notes": "NOTES-SENTINEL-n1"}


@pytest.fixture
def root(tmp_path):
    """syn-004 Accepted (rule, no call), syn-005 TLE (rule type + LLM explanation), syn-009 WA (LLM)."""
    syn = tmp_path / "evals" / "data" / "sessions" / "synthetic"
    syn.mkdir(parents=True)
    for sid in ("syn-004", "syn-005", "syn-009"):
        for ext in (".json", ".meta.json"):
            shutil.copy(SYN / f"{sid}{ext}", syn / f"{sid}{ext}")
    f = tmp_path / "evals" / "data" / "failure" / "dev" / "cases.jsonl"
    f.parent.mkdir(parents=True)
    rows = [_row(1, "syn-004", "none", ["rule_decided"], ["KEYFACT-SENTINEL-k1"]),
            _row(2, "syn-005", "too_slow", ["rule_decided"], ["KEYFACT-SENTINEL-k2"]),
            _row(3, "syn-009", "edge_case_missed", [], ["KEYFACT-SENTINEL-k3"])]
    f.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return tmp_path / "evals"


def test_the_runner_records_both_deciders_versions_and_cost(root, settings, tmp_path):
    from tutor.evals.runner import predictor_named, run, summary_line
    from tutor.prompts import load_prompt

    client, fake = _client(settings, [_ans("wrong_approach", "Rescans the stack."), _ans("edge_case_missed")])
    pred = predictor_named("failure", settings=settings, client=client)
    rec = run("failure", "dev", predictor=pred, settings=settings, root=root, results_dir=tmp_path / "results")

    assert len(fake.calls) == 2, "Accepted makes no call"
    assert rec["prompt_versions"] == {"failure": "v1"}
    assert rec["prompt_sha256"] == {"failure": load_prompt("failure", "v1").sha256}
    assert (rec["provider"], rec["model"]) == ("openai", "gpt-5.5")
    a = rec["aggregates"]
    assert a["by_decider"]["rule"] == {"accuracy": 1.0, "n": 2} and a["by_decider"]["llm"] == {"accuracy": 1.0, "n": 1}
    outs = {c["case_id"]: c for c in rec["cases"]}
    assert outs["failure-dev-001"]["output"] == {"failure_type": "none", "source": "rule", "explanation": None}
    assert outs["failure-dev-001"]["cost_usd"] == 0.0
    assert outs["failure-dev-002"]["output"] == {"failure_type": "too_slow", "source": "rule",
                                                 "explanation": "Rescans the stack."}
    assert rec["cost_usd_total"] == pytest.approx(0.04)
    assert "prompt failure-v1" in summary_line(rec)


def test_no_label_or_case_text_reaches_the_model(root, settings, tmp_path):
    from tutor.evals.runner import predictor_named, run

    client, fake = _client(settings, [_ans("wrong_approach"), _ans("implementation_bug")])
    run("failure", "dev", predictor=predictor_named("failure", settings=settings, client=client),
        settings=settings, root=root, results_dir=tmp_path / "results")
    sent = json.dumps([[m.model_dump() for m in c["messages"]] for c in fake.calls])
    leaked = [s for s in ("KEYFACT-SENTINEL", "NOTES-SENTINEL", "label_source", "rule_decided")
              if s in sent]
    assert not leaked, f"rule 1: case labels reached the model: {leaked}"
