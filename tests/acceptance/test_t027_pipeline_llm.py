"""Acceptance tests for T-027: `tutor analyze` writes the LLM fields (architecture §1, §3.2, §8.2).
Tester-owned (`/test write T-027`, 2026-11-07). Interfaces (D-057):

    analyze(settings, *, run_id, since=None, llm=False, client=None, model=None) -> AnalyzeReport
        AnalyzeReport gains `llm_errors: int`.
    tutor analyze [--since] [--llm [--model PROVIDER:MODEL]]
        Without --llm: facts and timelines only, as in T-011 (no calls, no spend).
        With --llm: also the failure and algorithm fields, through the SAME functions the eval
        runner calls (fields/failure.failure, fields/algorithm.algorithm), written to
        session_analysis (failure_type, failure_type_source, failure_explanation,
        condenser_version), session_algorithms (one row per label) and field_provenance (one row
        per field that made a call; a passed session's failure field makes none).
    T-031 (2026-11-08, `/test write`): `--llm` also writes the timeline field
    (session_analysis.timeline_summary + a `timeline_summary` provenance row per session), so the
    call and provenance counts below include it.
    Re-running replaces a session's rows (no duplicates). An LLM error in one field of one
    session is logged to pipeline.jsonl as `llm_field_failed` {session_id, field, error}, leaves
    that field NULL / without rows, and the run goes on. A config error (e.g. an unpriced model)
    raises before anything is written.
"""

import json
import sqlite3
from datetime import datetime, timedelta

import pytest

from _capture_fixture import build
from _llm_fake import FakeAdapter


def ts(base, minutes):
    t = datetime.fromisoformat(base.replace("Z", "+00:00")) + timedelta(minutes=minutes)
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


A, B, D = "s-pass", "s-unknown", "s-wrong"
A0, B0, D0 = "2026-11-01T14:00:00.000Z", "2026-11-01T20:00:00.000Z", "2026-11-03T02:00:00.000Z"
SESSIONS = [{"id": A, "started_at": A0}, {"id": B, "started_at": B0}, {"id": D, "started_at": D0}]
SNAPSHOTS = ([{"session_id": A, "ts": ts(A0, m), "code": f"a = {m}"} for m in (0, 3, 6)]
             + [{"session_id": B, "ts": ts(B0, m), "code": f"b = {m}"} for m in (0, 2, 5)]
             + [{"session_id": D, "ts": ts(D0, m), "code": f"d = {m}"} for m in (0, 1)])
JUDGE = [
    {"session_id": A, "ts": ts(A0, 7.5), "kind": "submit", "status": "Accepted", "tests_passed": 5,
     "tests_total": 5, "submission_id": "100"},
    {"session_id": B, "ts": ts(B0, 3), "kind": "run", "status": "Runtime Error", "submission_id": "runcode_2"},
    {"session_id": D, "ts": ts(D0, 2), "kind": "submit", "status": "Wrong Answer", "tests_passed": 3,
     "tests_total": 9, "submission_id": "200"},
]


class Router(FakeAdapter):
    """Answers by the requested schema, so the call order doesn't matter. `fail_if` text in the
    prompt raises a non-retryable provider error for that call."""

    def __init__(self, fail_if=None):
        super().__init__([])
        self.fail_if = fail_if

    def structured(self, **kw):
        from tutor.llm import LLMProviderError

        text = "".join(m.content for m in kw["messages"])
        if self.fail_if and self.fail_if in text and "failure_type" in json.dumps(kw["schema"]):
            self.calls.append(kw)
            raise LLMProviderError("provider down", retryable=False)
        if "algorithms" in json.dumps(kw["schema"]):
            self.script = [{"algorithms": ["hash_map", "two_pointers"]}]
        elif "summary" in json.dumps(kw["schema"]):   # T-031 adds the timeline field
            self.script = [{"summary": "You tried one idea. It ended as the verdict says."}]
        else:
            self.script = [{"failure_type": "implementation_bug", "explanation": "An index is off by one."}]
        return super().structured(**kw)


@pytest.fixture
def env(tmp_path, monkeypatch):
    capture = build(tmp_path / "capture.db", sessions=SESSIONS, snapshots=SNAPSHOTS, judge_events=JUDGE)
    monkeypatch.setenv("TUTOR__PATHS__CAPTURE_DB", str(capture))
    monkeypatch.setenv("TUTOR__PATHS__EVAL_CAPTURE_DB", str(tmp_path / "frozen-not-used.db"))
    monkeypatch.setenv("TUTOR__PATHS__ANALYSIS_DB", str(tmp_path / "analysis.db"))
    monkeypatch.setenv("TUTOR__PATHS__VERDICTS", str(tmp_path / "no-verdicts.csv"))
    monkeypatch.setenv("TUTOR__PATHS__LOGS", str(tmp_path / "logs"))
    from tutor.cli import main

    assert main(["migrate"]) == 0
    return tmp_path


def _run(env, fake, **kw):
    from tutor.analyzer.pipeline import analyze
    from tutor.config import load_settings
    from tutor.llm import LLMClient

    settings = load_settings()
    client = LLMClient(settings, adapters={"openai": fake}, sleep=lambda s: None)
    return analyze(settings, run_id=kw.pop("run_id", "run-t027"), llm=True, client=client, **kw)


def q(env, sql, *params):
    con = sqlite3.connect(env / "analysis.db")
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, params)]
    finally:
        con.close()


def test_llm_fields_are_written_for_every_session(env):
    report = _run(env, Router())
    assert report.stored == 3 and report.llm_errors == 0
    rows = {r["session_id"]: r for r in q(env, "SELECT * FROM session_analysis")}
    assert set(rows) == {A, B, D}
    assert (rows[A]["failure_type"], rows[A]["failure_type_source"], rows[A]["failure_explanation"]) == ("none", "rule", None)
    for s in (B, D):
        assert (rows[s]["failure_type"], rows[s]["failure_type_source"]) == ("implementation_bug", "llm")
        assert rows[s]["failure_explanation"] == "An index is off by one."
    assert all(r["condenser_version"] == "c1" for r in rows.values())
    labels = q(env, "SELECT session_id, label FROM session_algorithms ORDER BY session_id, label")
    assert labels == [{"session_id": s, "label": lab} for s in sorted((A, B, D)) for lab in ("hash_map", "two_pointers")]


def test_a_passed_session_makes_no_failure_call(env):
    fake = Router()
    _run(env, fake)
    failure_calls = [c for c in fake.calls if "failure_type" in json.dumps(c["schema"])]
    assert len(failure_calls) == 2 and len(fake.calls) == 8, "3 algorithm + 2 failure (A passed) + 3 timeline calls"


def test_provenance_names_prompt_model_run_and_call(env):
    _run(env, Router(), run_id="run-prov")
    prov = q(env, "SELECT * FROM field_provenance ORDER BY session_id, field")
    assert {(p["session_id"], p["field"]) for p in prov} == {(A, "algorithm"), (B, "algorithm"), (B, "failure"),
                                                            (D, "algorithm"), (D, "failure"),
                                                            (A, "timeline_summary"), (B, "timeline_summary"),
                                                            (D, "timeline_summary")}
    from tutor.config import load_settings

    pin = load_settings().prompts   # pinned version, not a literal: T-036 pins timeline v2 (`/test write` correction, 2026-11-08)
    assert all((p["prompt_version"], p["provider"], p["model"], p["run_id"])
               == (pin[p["prompt_name"]], "openai", "gpt-5.5", "run-prov") for p in prov)
    assert {p["prompt_name"] for p in prov} == {"algorithm", "failure", "timeline"}
    logged = {json.loads(x)["call_id"] for x in (env / "logs" / "llm_calls.jsonl").read_text().splitlines()}
    assert {p["call_id"] for p in prov} <= logged, "call_id joins to llm_calls.jsonl"


def test_rerunning_replaces_rows_without_duplicates(env):
    _run(env, Router(), run_id="run-1")
    _run(env, Router(), run_id="run-2")
    assert len(q(env, "SELECT * FROM session_analysis")) == 3
    assert len(q(env, "SELECT * FROM session_algorithms")) == 6
    prov = q(env, "SELECT run_id FROM field_provenance")
    assert len(prov) == 8 and {p["run_id"] for p in prov} == {"run-2"}


def test_an_llm_error_leaves_that_field_null_and_the_run_goes_on(env):
    report = _run(env, Router(fail_if="d = 1"))
    assert report.stored == 3 and report.llm_errors == 1
    d = q(env, "SELECT * FROM session_analysis WHERE session_id = ?", D)
    assert d and (d[0]["failure_type"], d[0]["failure_type_source"], d[0]["failure_explanation"]) == (None, None, None)
    assert len(q(env, "SELECT * FROM session_algorithms WHERE session_id = ?", D)) == 2, "the other field still lands"
    assert not q(env, "SELECT * FROM field_provenance WHERE session_id = ? AND field = 'failure'", D)
    b = q(env, "SELECT failure_type FROM session_analysis WHERE session_id = ?", B)
    assert b[0]["failure_type"] == "implementation_bug"
    events = [json.loads(x) for x in (env / "logs" / "pipeline.jsonl").read_text().splitlines()]
    failed = [e for e in events if e.get("event") == "llm_field_failed"]
    assert len(failed) == 1 and failed[0]["session_id"] == D and failed[0]["field"] == "failure"
    assert "provider down" in failed[0]["error"] and failed[0]["run_id"] == "run-t027"


def test_a_config_error_raises_before_anything_is_written(env):
    from tutor.llm import LLMConfigError
    from tutor.llm.client import ModelRef

    with pytest.raises(LLMConfigError):
        _run(env, Router(), model=ModelRef.parse("openai:unpriced-model"))
    assert q(env, "SELECT * FROM session_analysis") == []
    assert q(env, "SELECT * FROM field_provenance") == []


def test_without_llm_analyze_makes_no_calls_and_writes_no_llm_fields(env):
    from tutor.analyzer.pipeline import analyze
    from tutor.config import load_settings
    from tutor.llm import LLMClient

    settings = load_settings()
    fake = Router()
    report = analyze(settings, run_id="r", client=LLMClient(settings, adapters={"openai": fake}))
    assert report.stored == 3 and fake.calls == []
    assert q(env, "SELECT * FROM session_analysis") == [] and len(q(env, "SELECT * FROM sessions")) == 3


def test_the_cli_offers_llm_and_model_flags(capsys):
    from tutor.cli import main

    with pytest.raises(SystemExit):
        main(["analyze", "--help"])
    out = capsys.readouterr().out
    assert "--llm" in out and "--model" in out
