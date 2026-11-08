"""Acceptance tests for T-032: the runner runs LLM-judge graders (architecture §8.3, §8.4; rule 8).
Tester-owned (`/test write T-032`, 2026-11-08). Interfaces (D-061):

    An llm_judge grader has   name, version, kind = "llm_judge",
                              field: str          # LLMClient field: routes the model, names logged calls
                              run_id: str         # set by the runner to the record's run id
                              last_usage          # Usage | None, set by each grade() call
    and calls ctx.client.structured(...) inside grade().
    run(..., graders=None, judge_client=None)
        graders defaults to graders_for(suite); judge_client to LLMClient(settings).
        Every grader gets GradeContext(client=judge_client).
        Per row: judge_cost_usd. cost_usd_total = predictor cost + judge cost.
        A judge that raises makes that row an error ("judge: …"); the run goes on.
        aggregates.by_metric = {metric: {"mean", "n"}} over rows without an error.
        record["judge"] = {name, version, provider, model, calibrated} for the first llm_judge grader,
        else None. calibrated: `<root>/calibration.json` has an entry with that judge name and exact
        version and agreement >= 0.85.
    summary_line: "judge <name>-<version>", plus " (uncalibrated)" unless calibrated; "judge —" with none.
"""

import json
import shutil
from pathlib import Path

import pytest
from pydantic import BaseModel

from _llm_fake import FakeAdapter

REPO = Path(__file__).resolve().parents[2]
SYN = REPO / "evals" / "data" / "sessions" / "synthetic"


class Verdict(BaseModel):
    ok: bool


class FakeJudge:
    """A minimal judge: one structured call per grade, ok → 1.0."""

    name, version, kind, field = "fake-judge", "v1", "llm_judge", "fake_judge"

    def __init__(self):
        self.run_id = "unset"
        self.last_usage = None
        self.seen_clients = []

    def grade(self, case, output, ctx):
        from tutor.prompts import load_prompt

        from evals.graders.base import Grade

        self.last_usage = None
        self.seen_clients.append(ctx.client if ctx else None)
        r = ctx.client.structured(field=self.field, prompt=load_prompt("smoke", "v1"),
                                  variables={"problem_title": "x"}, output=Verdict, run_id=self.run_id)
        self.last_usage = r.usage
        return [Grade(metric="judge.ok", value=1.0 if r.output.ok else 0.0)]


class Exact:
    name, version, kind = "exact", "v1", "deterministic"

    def grade(self, case, output, ctx):
        from evals.graders.base import Grade

        return [Grade(metric="exact", value=1.0)]


class Echo:
    """A free local predictor, so every dollar in the record is the judge's."""

    name, version = "echo", "t-1"

    def __call__(self, session):
        return {"summary": "One. Two. Three."}


@pytest.fixture
def root(tmp_path):
    import sys

    sys.path.insert(0, str(REPO))
    syn = tmp_path / "evals" / "data" / "sessions" / "synthetic"
    syn.mkdir(parents=True)
    for sid in ("syn-004", "syn-009"):
        for ext in (".json", ".meta.json"):
            shutil.copy(SYN / f"{sid}{ext}", syn / f"{sid}{ext}")
    f = tmp_path / "evals" / "data" / "timeline" / "dev" / "cases.jsonl"
    f.parent.mkdir(parents=True)
    rows = [{"case_id": f"timeline-dev-{n:03d}", "suite": "timeline", "split": "dev", "dataset_version": "dev-v1",
             "source": "synthetic", "session": {"synthetic_path": f"evals/data/sessions/synthetic/{sid}.json"},
             "expected": {"checklist": {}, "key_facts": []}, "label_source": "human_written", "tags": [], "notes": ""}
            for n, sid in ((1, "syn-004"), (2, "syn-009"))]
    f.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return tmp_path / "evals"


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def _run(root, settings, tmp_path, script, judge=None):
    from tutor.evals.runner import run
    from tutor.llm import LLMClient

    judge = judge or FakeJudge()
    client = LLMClient(settings, adapters={"openai": FakeAdapter(script)}, sleep=lambda s: None)
    rec = run("timeline", "dev", predictor=Echo(), settings=settings, root=root, results_dir=tmp_path / "results",
              graders=[Exact(), judge], judge_client=client)
    return rec, judge, client


def _calibration(root, entries):
    (root / "calibration.json").write_text(json.dumps({"entries": entries}))


# ---------------------------------------------------------------- 1. context, logging, cost


def test_the_judge_gets_the_judge_client(root, settings, tmp_path):
    rec, judge, client = _run(root, settings, tmp_path, [{"ok": True}, {"ok": False}])
    assert judge.seen_clients == [client, client]
    grades = {c["case_id"]: {g["metric"]: g["value"] for g in c["grades"]} for c in rec["cases"]}
    assert grades == {"timeline-dev-001": {"exact": 1.0, "judge.ok": 1.0},
                      "timeline-dev-002": {"exact": 1.0, "judge.ok": 0.0}}


def test_judge_calls_are_logged_under_the_records_run_id(root, settings, tmp_path):
    rec, judge, _ = _run(root, settings, tmp_path, [{"ok": True}, {"ok": True}])
    assert judge.run_id == rec["run_id"]
    rows = [json.loads(x) for x in (settings.paths.logs / "llm_calls.jsonl").read_text().splitlines()]
    assert len(rows) == 2 and {(r["field"], r["run_id"]) for r in rows} == {("fake_judge", rec["run_id"])}


def test_judge_cost_is_in_each_row_and_the_total(root, settings, tmp_path):
    rec, _, _ = _run(root, settings, tmp_path, [{"ok": True}, {"ok": True}])
    per_call = (1000 * 5.0 + 500 * 30.0) / 1_000_000          # FakeAdapter tokens at gpt-5.5's price
    assert [c["judge_cost_usd"] for c in rec["cases"]] == [pytest.approx(per_call)] * 2
    assert all(c["cost_usd"] == 0.0 for c in rec["cases"]), "the predictor is free"
    assert rec["cost_usd_total"] == pytest.approx(2 * per_call)


def test_a_failing_judge_is_a_scored_error_and_the_run_goes_on(root, settings, tmp_path):
    from tutor.llm import LLMProviderError

    rec, _, _ = _run(root, settings, tmp_path, [LLMProviderError("judge down", retryable=False), {"ok": True}])
    errs = {c["case_id"]: c["error"] for c in rec["cases"]}
    assert errs["timeline-dev-001"].startswith("judge: ") and "judge down" in errs["timeline-dev-001"]
    assert errs["timeline-dev-002"] is None
    assert rec["aggregates"]["errors"] == 1


def test_by_metric_reports_every_metric(root, settings, tmp_path):
    rec, _, _ = _run(root, settings, tmp_path, [{"ok": True}, {"ok": False}])
    assert rec["aggregates"]["by_metric"] == {"exact": {"mean": 1.0, "n": 2}, "judge.ok": {"mean": 0.5, "n": 2}}


# ---------------------------------------------------------------- 2. record["judge"] and calibration


def test_the_record_names_the_judge_and_its_model(root, settings, tmp_path):
    rec, _, _ = _run(root, settings, tmp_path, [{"ok": True}, {"ok": True}])
    assert rec["judge"] == {"name": "fake-judge", "version": "v1", "provider": "openai", "model": "gpt-5.5",
                            "calibrated": False}


@pytest.mark.parametrize("entries,calibrated", [
    (None, False),                                                                   # no calibration file
    ([], False),
    ([{"judge": "fake-judge", "version": "v1", "agreement": 0.84, "n": 20, "decision": "revise"}], False),
    ([{"judge": "fake-judge", "version": "v0", "agreement": 0.95, "n": 20, "decision": "accept"}], False),
    ([{"judge": "other-judge", "version": "v1", "agreement": 0.95, "n": 20, "decision": "accept"}], False),
    ([{"judge": "fake-judge", "version": "v1", "agreement": 0.85, "n": 20, "decision": "accept"}], True),
])
def test_calibrated_needs_that_exact_version_at_085(root, settings, tmp_path, entries, calibrated):
    if entries is not None:
        _calibration(root, entries)
    rec, _, _ = _run(root, settings, tmp_path, [{"ok": True}, {"ok": True}])
    assert rec["judge"]["calibrated"] is calibrated


def test_no_judge_means_judge_none(root, settings, tmp_path):
    from tutor.evals.runner import run, summary_line

    rec = run("timeline", "dev", predictor=Echo(), settings=settings, root=root, results_dir=tmp_path / "results",
              graders=[Exact()])
    assert rec["judge"] is None and "judge —" in summary_line(rec)


# ---------------------------------------------------------------- 3. summary_line


def test_summary_line_names_the_judge_and_flags_uncalibrated(root, settings, tmp_path):
    from tutor.evals.runner import summary_line

    rec, _, _ = _run(root, settings, tmp_path, [{"ok": True}, {"ok": True}])
    assert "judge fake-judge-v1 (uncalibrated)" in summary_line(rec)


def test_summary_line_drops_the_flag_once_calibrated(root, settings, tmp_path):
    from tutor.evals.runner import summary_line

    _calibration(root, [{"judge": "fake-judge", "version": "v1", "agreement": 0.9, "n": 20, "decision": "accept"}])
    rec, _, _ = _run(root, settings, tmp_path, [{"ok": True}, {"ok": True}])
    line = summary_line(rec)
    assert "judge fake-judge-v1" in line and "uncalibrated" not in line


def test_the_committed_calibration_file_is_well_formed():
    data = json.loads((REPO / "evals" / "calibration.json").read_text())
    assert isinstance(data["entries"], list)
    for e in data["entries"]:
        assert set(e) >= {"judge", "version", "agreement", "n", "decision"} and 0 <= e["agreement"] <= 1
