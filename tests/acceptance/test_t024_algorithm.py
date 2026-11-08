"""Acceptance tests for T-024: the algorithm field and its runner predictor.
Tester-owned (`/test write T-024`, 2026-11-07). Interfaces (D-054):

    tutor.fields.algorithm
        PROMPT = "algorithm"                          # version pinned in tutor.toml [prompts]
        class AlgorithmOutput(BaseModel): algorithms: list[AlgorithmLabel]   # 1..2 items
        algorithm(session, *, client, settings, run_id, model=None) -> LLMResult[AlgorithmOutput]
    tutor.evals.runner.predictor_named("algorithm", *, settings, client=None, model=None)
        -> a predictor whose output is {"labels": [...]}, with .name "algorithm", .version = the
           prompt version, .provider, .prompt_versions, .prompt_sha256, and .last_usage (the
           LLMResult usage of its latest call) so the runner records cost and tokens per case.
    The record's `model` for an LLM predictor is the model id ("gpt-5.5"), `provider` "openai";
    summary_line names "prompt algorithm-v1" and "model openai:gpt-5.5".
    tutor-eval run|estimate accept --model PROVIDER:MODEL.

No network: the provider adapter is `tests/_llm_fake.FakeAdapter`. The real dev run is a Done-when
for the builder (recorded in the task log), not a test.
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
FINAL = "class Solution:\n    def twoSum(self, nums, target):\n        seen = {}\n        return []\n"


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def _client(settings, script):
    from tutor.llm import LLMClient

    fake = FakeAdapter(script)
    return LLMClient(settings, adapters={"openai": fake}, sleep=lambda s: None), fake


def _session():
    from tutor.models import Problem, Session, Snapshot

    return Session(session_id="t024-1",
                   problem=Problem(slug="two-sum", title="Two Sum", difficulty="Easy",
                                   tags=["array", "hash-table"], description=None),
                   snapshots=[Snapshot(ts=T0, code="# start\n", language="python3"),
                              Snapshot(ts=T0 + timedelta(minutes=4), code=FINAL, language="python3")],
                   events=[], submit_capture_reliable=True)


# ---------------------------------------------------------------- 1. the field


def test_algorithm_returns_the_labels_from_one_structured_call(settings):
    from tutor.fields.algorithm import algorithm
    from tutor.models import AlgorithmLabel

    client, fake = _client(settings, [{"algorithms": ["hash_map"]}])
    r = algorithm(_session(), client=client, settings=settings, run_id="r1")
    assert r.output.algorithms == [AlgorithmLabel.HASH_MAP]
    assert len(fake.calls) == 1 and r.attempts == 1


def test_the_input_has_the_final_code_title_and_tags(settings):
    from tutor.fields.algorithm import algorithm

    client, fake = _client(settings, [{"algorithms": ["hash_map"]}])
    algorithm(_session(), client=client, settings=settings, run_id="r1")
    text = "".join(m.content for m in fake.calls[0]["messages"])
    assert "seen = {}" in text and "Two Sum" in text
    assert "array" in text and "hash-table" in text


@pytest.mark.parametrize("bad", [[], ["hash_map", "stack", "heap"], ["sorting"]])
def test_zero_three_or_unknown_labels_are_invalid_and_retried(settings, bad):
    from tutor.fields.algorithm import algorithm

    client, fake = _client(settings, [{"algorithms": bad}, {"algorithms": ["two_pointers", "hash_map"]}])
    r = algorithm(_session(), client=client, settings=settings, run_id="r1")
    assert r.attempts == 2 and [a.value for a in r.output.algorithms] == ["two_pointers", "hash_map"]


def test_the_call_is_logged_with_field_and_prompt_version(settings):
    from tutor.fields.algorithm import algorithm

    client, _ = _client(settings, [{"algorithms": ["hash_map"]}])
    algorithm(_session(), client=client, settings=settings, run_id="r-log")
    rows = [json.loads(x) for x in (settings.paths.logs / "llm_calls.jsonl").read_text().splitlines()]
    assert rows and rows[-1]["field"] == "algorithm" and rows[-1]["prompt_version"] == "v1"
    assert rows[-1]["run_id"] == "r-log"


def test_an_explicit_model_is_used(settings, tmp_path):
    from tutor.fields.algorithm import algorithm
    from tutor.llm import LLMClient
    from tutor.llm.client import ModelRef

    pricing = tmp_path / "pricing.toml"   # the client refuses an unpriced model (T-006), so price the probe one
    pricing.write_text('[models."openai:gpt-other"]\ninput_per_mtok = 1.0\noutput_per_mtok = 2.0\nas_of = \"2026-11-07\"\n')
    fake = FakeAdapter([{"algorithms": ["hash_map"]}])
    client = LLMClient(settings, adapters={"openai": fake}, pricing_path=pricing, sleep=lambda s: None)
    algorithm(_session(), client=client, settings=settings, run_id="r1", model=ModelRef.parse("openai:gpt-other"))
    assert fake.calls[0]["model"] == "gpt-other"


# ---------------------------------------------------------------- 2. the prompt file


def test_the_prompt_is_a_versioned_file_pinned_in_config(settings):
    from tutor.prompts import load_prompt

    assert settings.prompts.get("algorithm") == "v1", "tutor.toml [prompts] pins algorithm = \"v1\""
    p = load_prompt("algorithm", "v1")
    manifest = json.loads((REPO / "prompts" / "manifest.json").read_text())
    assert manifest.get("algorithm/v1.md") == p.sha256
    assert "final_code" in p.variables


def test_the_prompt_lists_every_label_and_no_dataset_example():
    from tutor.models import AlgorithmLabel

    text = (REPO / "prompts" / "algorithm" / "v1.md").read_text()
    missing = [a.value for a in AlgorithmLabel if a.value not in text]
    assert not missing, f"the prompt must offer every label: {missing}"
    slugs = {json.loads(r)["problem"]["slug"] for r in (SYN / "specs.jsonl").read_text().splitlines() if r.strip()}
    named = [s for s in slugs if s in text]
    assert not named, f"rule 9: the prompt names dataset problems {named}"


# ---------------------------------------------------------------- 3. through the runner


def _case(n, sid, labels):
    return {"case_id": f"algorithm-dev-{n:03d}", "suite": "algorithm", "split": "dev", "dataset_version": "dev-v1",
            "source": "synthetic", "session": {"synthetic_path": f"evals/data/sessions/synthetic/{sid}.json"},
            "expected": {"labels": labels}, "label_source": "human_written", "tags": [], "notes": ""}


@pytest.fixture
def root(tmp_path):
    syn = tmp_path / "evals" / "data" / "sessions" / "synthetic"
    syn.mkdir(parents=True)
    for sid in ("syn-001", "syn-005"):
        for ext in (".json", ".meta.json"):
            shutil.copy(SYN / f"{sid}{ext}", syn / f"{sid}{ext}")
    f = tmp_path / "evals" / "data" / "algorithm" / "dev" / "cases.jsonl"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps(_case(1, "syn-001", ["two_pointers"])) + "\n" + json.dumps(_case(2, "syn-005", ["stack"])) + "\n")
    return tmp_path / "evals"


def test_the_runner_records_versions_cost_and_accuracy_for_the_llm_predictor(root, settings, tmp_path):
    from tutor.evals.runner import predictor_named, run, summary_line
    from tutor.prompts import load_prompt

    client, fake = _client(settings, [{"algorithms": ["two_pointers"]}, {"algorithms": ["heap"]}])
    pred = predictor_named("algorithm", settings=settings, client=client)
    rec = run("algorithm", "dev", predictor=pred, settings=settings, root=root, results_dir=tmp_path / "results")

    assert (rec["provider"], rec["model"]) == ("openai", "gpt-5.5")
    assert rec["prompt_versions"] == {"algorithm": "v1"}
    assert rec["prompt_sha256"] == {"algorithm": load_prompt("algorithm", "v1").sha256}
    assert rec["aggregates"]["accuracy"] == 0.5 and rec["aggregates"]["errors"] == 0
    assert [c["output"] for c in rec["cases"]] == [{"labels": ["two_pointers"]}, {"labels": ["heap"]}]
    # FakeAdapter bills 1000 in / 500 out per call; gpt-5.5 is $5 / $30 per 1M → $0.02 per call
    assert all(c["input_tokens"] == 1000 and c["output_tokens"] == 500 for c in rec["cases"])
    assert rec["cost_usd_total"] == pytest.approx(0.04)
    line = summary_line(rec)
    assert "prompt algorithm-v1" in line and "model openai:gpt-5.5" in line and "dataset dev-v1" in line


def test_the_runner_hands_the_field_no_label(root, settings, tmp_path):
    from tutor.evals.runner import predictor_named, run

    client, fake = _client(settings, [{"algorithms": ["stack"]}] * 2)
    run("algorithm", "dev", predictor=predictor_named("algorithm", settings=settings, client=client),
        settings=settings, root=root, results_dir=tmp_path / "results")
    sent = json.dumps([[m.model_dump() for m in c["messages"]] for c in fake.calls])
    assert "label_source" not in sent and "human_written" not in sent and "expected" not in sent


def test_a_provider_error_is_a_scored_error_not_a_crash(root, settings, tmp_path):
    from tutor.evals.runner import predictor_named, run
    from tutor.llm.errors import LLMProviderError

    client, _ = _client(settings, [LLMProviderError("boom", retryable=False), {"algorithms": ["stack"]}])
    rec = run("algorithm", "dev", predictor=predictor_named("algorithm", settings=settings, client=client),
              settings=settings, root=root, results_dir=tmp_path / "results")
    assert rec["aggregates"]["errors"] == 1 and rec["aggregates"]["accuracy"] == 0.5


def test_predictor_named_takes_a_model(settings):
    from tutor.evals.runner import predictor_named
    from tutor.llm.client import ModelRef

    pred = predictor_named("algorithm", settings=settings, model=ModelRef.parse("openai:gpt-other"))
    assert pred.name == "algorithm" and pred.version == "v1" and pred.provider == "openai"


def test_tutor_eval_accepts_a_model_flag(capsys):
    from tutor.cli import eval_main

    for cmd in ("run", "estimate"):
        with pytest.raises(SystemExit):
            eval_main([cmd, "--help"])
        assert "--model" in capsys.readouterr().out
