"""Acceptance tests for T-006: LLM client wrapper `structured()`, pricing, call log.

Tester-owned (`/test write T-006`, 2026-11-03). Black-box against architecture §6.1, §6.4, §6.5
and the interfaces the human approved in D-027:

    tutor.llm: LLMClient, ModelRef, LLMResult, Usage,
               LLMError, LLMConfigError, LLMOutputInvalid, LLMProviderError
    LLMClient(settings, *, adapters: Mapping[str, Adapter] | None = None,
              pricing_path: Path | None = None,      # default config/pricing.toml
              sleep: Callable[[float], None] = time.sleep)
    ModelRef.parse("provider:model") -> ModelRef      # malformed / unknown provider -> LLMConfigError
    LLMProviderError(message, *, retryable: bool, status_code: int | None = None)
        adapters raise it; the client retries only when retryable is True
    The client passes adapters `schema=output.model_json_schema()` unchanged; strict-mode
    rewriting is the adapter's job.
    Model choice: `model=` argument > `llm.fields.<field>` > `llm.default`. (The `--model` CLI
    flag is T-007's.)
    Backoff before transient retry k (1-based): 2**k seconds + jitter in [0, 1).
    LLMResult.usage sums tokens and cost over every attempt of the call.

The provider is `tests/_llm_fake.py`'s FakeAdapter; nothing here touches a network. The real
OpenAI adapter is checked in tests/contract/test_openai_adapter.py.
"""

import json
from datetime import datetime
from typing import Annotated

import pytest
from pydantic import AfterValidator, BaseModel

from _llm_fake import FakeAdapter

PROMPT = """---
name: demo
version: v1
field: algorithm
variables: [problem_title]
output_schema: AlgoOut
---
Name the algorithm for $problem_title.
"""
FILLED = "Name the algorithm for Two Sum.\n"

PRICING = """
[models."openai:gpt-5.5"]
input_per_mtok = 1.00
output_per_mtok = 2.00
as_of = "2026-11-03"

[models."openai:gpt-field"]
input_per_mtok = 1.00
output_per_mtok = 2.00
as_of = "2026-11-03"

[models."openai:gpt-arg"]
input_per_mtok = 1.00
output_per_mtok = 2.00
as_of = "2026-11-03"

[models."gemini:gemini-x"]
input_per_mtok = 1.00
output_per_mtok = 2.00
as_of = "2026-11-03"
"""
# FakeAdapter reports 1000 input + 500 output tokens per attempt: 1000 * 1/1e6 + 500 * 2/1e6
COST_PER_ATTEMPT = 0.002

LOG_FIELDS = {"ts", "run_id", "call_id", "attempt", "kind", "field", "prompt_name", "prompt_version",
              "prompt_sha256", "provider", "model", "input_tokens", "output_tokens", "cost_usd",
              "latency_ms", "outcome", "error"}

GOOD = {"algorithm": "hash map", "confidence": 0.9}


def _lower_case(v: str) -> str:
    if v != v.lower():
        raise ValueError("algorithm must be lower-case")
    return v


class AlgoOut(BaseModel):
    # The validator can't be expressed in JSON schema, so only pydantic catches it (Done-when 1).
    algorithm: Annotated[str, AfterValidator(_lower_case)]
    confidence: float


# ---------------------------------------------------------------- helpers


def llm():
    import tutor.llm

    return tutor.llm


@pytest.fixture
def env(tmp_path):
    return {"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}


@pytest.fixture
def pricing(tmp_path):
    p = tmp_path / "pricing.toml"
    p.write_text(PRICING)
    return p


@pytest.fixture
def prompt(tmp_path):
    from tutor.prompts import load_prompt

    (tmp_path / "prompts" / "demo").mkdir(parents=True)
    (tmp_path / "prompts" / "demo" / "v1.md").write_text(PROMPT)
    return load_prompt("demo", "v1", root=tmp_path / "prompts")


class Sleeps(list):
    def __call__(self, seconds):
        self.append(seconds)


def make(tmp_path, env, fake, *, pricing=None, sleep=None, extra_env=None):
    from tutor.config import load_settings

    settings = load_settings(env={**env, **(extra_env or {})}, dotenv_path=tmp_path / "none.env")
    kw = {"adapters": {"openai": fake}, "sleep": sleep if sleep is not None else Sleeps()}
    if pricing is not None:
        kw["pricing_path"] = pricing
    return llm().LLMClient(settings, **kw)


def call(client, prompt, **kw):
    args = {"field": "algorithm", "prompt": prompt, "variables": {"problem_title": "Two Sum"},
            "output": AlgoOut, "run_id": "run-t006"}
    return client.structured(**{**args, **kw})


def log_lines(tmp_path):
    path = tmp_path / "logs" / "llm_calls.jsonl"
    assert path.is_file(), "every attempt writes a line to <paths.logs>/llm_calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def provider_error(retryable, status=None):
    return llm().LLMProviderError("simulated provider failure", retryable=retryable, status_code=status)


# ---------------------------------------------------------------- Done-when 1: structured() per §6.1


def test_structured_returns_a_validated_result(tmp_path, env, pricing, prompt):
    fake = FakeAdapter([GOOD])
    r = call(make(tmp_path, env, fake, pricing=pricing), prompt)
    assert isinstance(r.output, AlgoOut) and r.output.algorithm == "hash map"
    assert r.attempts == 1
    assert (r.usage.input_tokens, r.usage.output_tokens) == (1000, 500)
    assert r.usage.cost_usd == pytest.approx(COST_PER_ATTEMPT)
    assert isinstance(r.call_id, str) and r.call_id
    assert isinstance(r.latency_ms, int) and r.latency_ms >= 0


def test_the_filled_prompt_and_the_output_schema_reach_the_adapter(tmp_path, env, pricing, prompt):
    from tutor.llm.messages import Message

    fake = FakeAdapter([GOOD])
    call(make(tmp_path, env, fake, pricing=pricing), prompt)
    [kw] = fake.calls
    assert all(isinstance(m, Message) for m in kw["messages"])
    assert FILLED in [m.content for m in kw["messages"]], "the prompt filled with `variables` is sent"
    assert kw["schema"] == AlgoOut.model_json_schema()
    assert kw["timeout_s"] == 60, "llm.timeout_s from tutor.toml"


def test_output_is_validated_by_pydantic_even_when_it_matches_the_json_schema(tmp_path, env, pricing, prompt):
    # "Hash Map" is a valid string for the JSON schema but fails the pydantic validator.
    fake = FakeAdapter([{"algorithm": "Hash Map", "confidence": 0.9}, GOOD])
    r = call(make(tmp_path, env, fake, pricing=pricing), prompt)
    assert r.attempts == 2 and r.output.algorithm == "hash map"


def test_model_comes_from_llm_default(tmp_path, env, pricing, prompt):
    fake = FakeAdapter([GOOD])
    call(make(tmp_path, env, fake, pricing=pricing), prompt, field="failure")
    assert fake.calls[0]["model"] == "gpt-5.5"
    assert (log_lines(tmp_path)[0]["provider"], log_lines(tmp_path)[0]["model"]) == ("openai", "gpt-5.5")


def test_a_per_field_model_beats_the_default(tmp_path, env, pricing, prompt):
    fake = FakeAdapter([GOOD, GOOD])
    client = make(tmp_path, env, fake, pricing=pricing, extra_env={"TUTOR__LLM__FIELDS__TIMELINE": "openai:gpt-field"})
    call(client, prompt, field="timeline")
    call(client, prompt, field="failure")
    assert [c["model"] for c in fake.calls] == ["gpt-field", "gpt-5.5"]


def test_an_explicit_model_beats_field_and_default(tmp_path, env, pricing, prompt):
    fake = FakeAdapter([GOOD])
    client = make(tmp_path, env, fake, pricing=pricing, extra_env={"TUTOR__LLM__FIELDS__TIMELINE": "openai:gpt-field"})
    call(client, prompt, field="timeline", model=llm().ModelRef.parse("openai:gpt-arg"))
    assert fake.calls[0]["model"] == "gpt-arg"
    assert log_lines(tmp_path)[0]["model"] == "gpt-arg"


def test_model_ref_parses_provider_and_model():
    ref = llm().ModelRef.parse("openai:gpt-5.5")
    assert (ref.provider, ref.model) == ("openai", "gpt-5.5")


@pytest.mark.parametrize("text", ["gpt-5.5", "mistral:large", "openai:", ":gpt-5.5", ""])
def test_a_malformed_model_ref_is_a_config_error(text):
    with pytest.raises(llm().LLMConfigError):
        llm().ModelRef.parse(text)


# ---------------------------------------------------------------- Done-when 3: retry and error table §6.4


def test_invalid_output_is_retried_once_with_the_validation_error_appended(tmp_path, env, pricing, prompt):
    fake = FakeAdapter(["not json at all", GOOD])
    r = call(make(tmp_path, env, fake, pricing=pricing), prompt)
    assert r.attempts == 2
    first, second = fake.calls[0]["messages"], fake.calls[1]["messages"]
    assert second[: len(first)] == first, "the retry keeps the original conversation"
    assert len(second) > len(first)
    assert second[-1].role == "user", "the validation error is appended as a user message"


def test_the_appended_message_names_what_was_wrong(tmp_path, env, pricing, prompt):
    fake = FakeAdapter([{"algorithm": "two pointers"}, GOOD])  # `confidence` missing
    call(make(tmp_path, env, fake, pricing=pricing), prompt)
    assert "confidence" in fake.calls[1]["messages"][-1].content


def test_invalid_output_twice_raises_llm_output_invalid(tmp_path, env, pricing, prompt):
    fake = FakeAdapter(["nope", "still nope", GOOD])
    with pytest.raises(llm().LLMOutputInvalid):
        call(make(tmp_path, env, fake, pricing=pricing), prompt)
    assert len(fake.calls) == 2, "1 retry (llm.max_output_retries = 1), so 2 attempts"
    assert [line["outcome"] for line in log_lines(tmp_path)] == ["invalid_output", "invalid_output"]


def test_max_output_retries_comes_from_config(tmp_path, env, pricing, prompt):
    fake = FakeAdapter(["a", "b", "c", GOOD])
    r = call(make(tmp_path, env, fake, pricing=pricing, extra_env={"TUTOR__LLM__MAX_OUTPUT_RETRIES": "3"}), prompt)
    assert r.attempts == 4


def test_transient_errors_are_retried_three_times_with_backoff(tmp_path, env, pricing, prompt):
    sleeps = Sleeps()
    fake = FakeAdapter([provider_error(True, 429), provider_error(True, 500), provider_error(True, None), GOOD])
    r = call(make(tmp_path, env, fake, pricing=pricing, sleep=sleeps), prompt)
    assert r.attempts == 4 and len(fake.calls) == 4
    assert len(sleeps) == 3
    for base, s in zip((2, 4, 8), sleeps):
        assert base <= s < base + 1, f"backoff {s}s is not {base}s + jitter in [0, 1)"


def test_transient_errors_past_the_limit_raise_llm_provider_error(tmp_path, env, pricing, prompt):
    sleeps = Sleeps()
    fake = FakeAdapter([provider_error(True, 503)] * 4 + [GOOD])
    with pytest.raises(llm().LLMProviderError):
        call(make(tmp_path, env, fake, pricing=pricing, sleep=sleeps), prompt)
    assert len(fake.calls) == 4 and len(sleeps) == 3
    assert [line["outcome"] for line in log_lines(tmp_path)] == ["provider_error"] * 4


def test_max_transient_retries_comes_from_config(tmp_path, env, pricing, prompt):
    fake = FakeAdapter([provider_error(True, 429)] * 3 + [GOOD])
    with pytest.raises(llm().LLMProviderError):
        call(make(tmp_path, env, fake, pricing=pricing, extra_env={"TUTOR__LLM__MAX_TRANSIENT_RETRIES": "1"}), prompt)
    assert len(fake.calls) == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_a_non_retryable_error_is_not_retried(tmp_path, env, pricing, prompt, status):
    sleeps = Sleeps()
    fake = FakeAdapter([provider_error(False, status), GOOD])
    with pytest.raises(llm().LLMProviderError):
        call(make(tmp_path, env, fake, pricing=pricing, sleep=sleeps), prompt)
    assert len(fake.calls) == 1 and sleeps == []


def test_error_types_share_a_base():
    m = llm()
    for cls in (m.LLMConfigError, m.LLMOutputInvalid, m.LLMProviderError):
        assert issubclass(cls, m.LLMError)


# ---------------------------------------------------------------- Done-when 3: config errors before any call


def _config_error_before_any_call(tmp_path, env, prompt, **make_kw):
    fake = FakeAdapter([GOOD])
    with pytest.raises(llm().LLMConfigError):
        call(make(tmp_path, env, fake, **make_kw), prompt)
    assert fake.calls == [], "LLMConfigError must be raised before the provider is called"


def test_a_model_without_a_price_fails_before_calling(tmp_path, env, pricing, prompt):
    _config_error_before_any_call(tmp_path, env, prompt, pricing=pricing,
                                  extra_env={"TUTOR__LLM__DEFAULT": "openai:gpt-unpriced"})


def test_a_provider_without_an_adapter_fails_before_calling(tmp_path, env, pricing, prompt):
    # Priced, but no gemini adapter exists (it arrives at build step 7).
    _config_error_before_any_call(tmp_path, env, prompt, pricing=pricing,
                                  extra_env={"TUTOR__LLM__DEFAULT": "gemini:gemini-x"})


@pytest.mark.parametrize("ref", ["gpt-5.5", "mistral:large"])
def test_a_malformed_configured_model_fails_before_calling(tmp_path, env, pricing, prompt, ref):
    fake = FakeAdapter([GOOD])
    from tutor.config import ConfigError

    with pytest.raises((llm().LLMConfigError, ConfigError)):
        call(make(tmp_path, env, fake, pricing=pricing, extra_env={"TUTOR__LLM__DEFAULT": ref}), prompt)
    assert fake.calls == []


def test_a_missing_pricing_file_is_a_config_error(tmp_path, env, prompt):
    _config_error_before_any_call(tmp_path, env, prompt, pricing=tmp_path / "no-such-pricing.toml")


# Missing API key: checked on the real OpenAI adapter in tests/contract/test_openai_adapter.py.


# ---------------------------------------------------------------- Done-when 4: one log line per attempt


def test_every_attempt_writes_one_line_with_all_fields(tmp_path, env, pricing, prompt):
    fake = FakeAdapter([provider_error(True, 429), "not json", GOOD])
    r = call(make(tmp_path, env, fake, pricing=pricing), prompt)
    lines = log_lines(tmp_path)
    assert len(lines) == 3
    for n, line in enumerate(lines, 1):
        assert LOG_FIELDS <= line.keys(), f"missing: {sorted(LOG_FIELDS - line.keys())}"
        assert line["attempt"] == n
        assert line["call_id"] == r.call_id
        assert line["run_id"] == "run-t006"
        assert line["kind"] == "structured"
        assert line["field"] == "algorithm"
        assert (line["prompt_name"], line["prompt_version"], line["prompt_sha256"]) == ("demo", "v1", prompt.sha256)
        assert datetime.fromisoformat(line["ts"]).tzinfo is not None
        assert isinstance(line["latency_ms"], int) and line["latency_ms"] >= 0
    assert [line["outcome"] for line in lines] == ["provider_error", "invalid_output", "ok"]
    assert lines[2]["error"] is None
    assert lines[0]["error"] and lines[1]["error"], "a failed attempt records why"


def test_a_failed_provider_attempt_costs_nothing(tmp_path, env, pricing, prompt):
    fake = FakeAdapter([provider_error(True, 500), GOOD])
    call(make(tmp_path, env, fake, pricing=pricing), prompt)
    first, second = log_lines(tmp_path)
    assert (first["input_tokens"], first["output_tokens"], first["cost_usd"]) == (0, 0, 0.0)
    assert (second["input_tokens"], second["output_tokens"]) == (1000, 500)
    assert second["cost_usd"] == pytest.approx(COST_PER_ATTEMPT)


def test_usage_sums_every_attempt(tmp_path, env, pricing, prompt):
    fake = FakeAdapter(["not json", GOOD])
    r = call(make(tmp_path, env, fake, pricing=pricing), prompt)
    assert (r.usage.input_tokens, r.usage.output_tokens) == (2000, 1000)
    assert r.usage.cost_usd == pytest.approx(2 * COST_PER_ATTEMPT)
    assert sum(line["cost_usd"] for line in log_lines(tmp_path)) == pytest.approx(r.usage.cost_usd)


def test_two_calls_get_different_call_ids(tmp_path, env, pricing, prompt):
    fake = FakeAdapter([GOOD, GOOD])
    client = make(tmp_path, env, fake, pricing=pricing)
    a, b = call(client, prompt), call(client, prompt)
    assert a.call_id != b.call_id
    assert {line["call_id"] for line in log_lines(tmp_path)} == {a.call_id, b.call_id}


def test_bodies_go_to_their_own_file_not_the_main_log(tmp_path, env, pricing, prompt):
    fake = FakeAdapter([GOOD])
    r = call(make(tmp_path, env, fake, pricing=pricing), prompt)
    body = tmp_path / "logs" / "llm_bodies" / f"{r.call_id}.json"
    assert body.is_file()
    text = body.read_text()
    json.loads(text)
    assert "Name the algorithm for Two Sum." in text, "the request is kept for debugging"
    assert "hash map" in text, "the response is kept for debugging"
    assert "Name the algorithm for Two Sum." not in (tmp_path / "logs" / "llm_calls.jsonl").read_text()


def test_cost_uses_config_pricing_toml_by_default(tmp_path, env, prompt):
    # config/pricing.toml: openai:gpt-5.5 at $5.00 in / $30.00 out per 1M tokens.
    fake = FakeAdapter([GOOD])
    r = call(make(tmp_path, env, fake), prompt)
    assert r.usage.cost_usd == pytest.approx(1000 * 5.00 / 1e6 + 500 * 30.00 / 1e6)
