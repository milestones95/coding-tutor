"""Contract: the real Anthropic adapter, against a fake Messages API on loopback — architecture
§6.1, §6.4, §6.5; rule 5; D-027, D-047. Tester-owned (`/test write T-015`, 2026-11-07).

`LLMClient` runs with no injected adapters, so the production path is exercised: the client, the
real `adapters/anthropic.py`, the real `anthropic` SDK, then HTTP to `ANTHROPIC_BASE_URL`.

What this protects:
- Native structured output: `output_config.format` is a `json_schema` whose objects are all closed
  (`additionalProperties: false`). No thinking-disable and no sampling parameters, both of which
  Opus 5.5 rejects with a 400.
- The JSON is read from the `text` block even though a `thinking` block comes first.
- Only the client retries: SDK retries are off, so a failing server sees 1 + 3 requests. 429, 5xx
  and timeouts are retried; other 4xx are not.
- A refusal (`stop_reason: "refusal"`) is an `LLMProviderError`, not retried (D-047).
- The key comes from `ANTHROPIC_API_KEY` and is never written to a log, a body file or an error.
  A missing key is an `LLMConfigError` before any request.
"""

import json

import pytest
from pydantic import BaseModel

from _fake_anthropic import start_fake_anthropic

# T-015 is deferred to M7 (D-048): the human writes the synthetic sessions, so no in-repo caller
# needs Claude until the model comparison. Kept, not deleted; remove this mark when T-015 resumes.
pytestmark = pytest.mark.skip(reason="T-015 Anthropic adapter deferred to M7 (D-048)")

KEY = "sk-ant-SENTINEL-t015-never-logged-77c2"
MODEL = "anthropic:claude-opus-5-5"
FILLED = "Name the algorithm for Two Sum."
PROMPT = """---
name: demo
version: v1
field: algorithm
variables: [problem_title]
output_schema: AlgoOut
---
Name the algorithm for $problem_title.
"""
OUTPUT = {"algorithm": "hash map", "confidence": 0.9}


class Inner(BaseModel):
    note: str


class AlgoOut(BaseModel):
    algorithm: str
    confidence: float


class Nested(BaseModel):
    algorithm: str
    detail: Inner


@pytest.fixture
def server(monkeypatch):
    s = start_fake_anthropic(monkeypatch, key=KEY, output=OUTPUT)
    yield s
    s.close()


@pytest.fixture
def prompt(tmp_path):
    from tutor.prompts import load_prompt

    (tmp_path / "prompts" / "demo").mkdir(parents=True)
    (tmp_path / "prompts" / "demo" / "v1.md").write_text(PROMPT)
    return load_prompt("demo", "v1", root=tmp_path / "prompts")


class Sleeps(list):
    def __call__(self, seconds):
        self.append(seconds)


def client(tmp_path, sleeps=None, **env):
    from tutor.config import load_settings
    from tutor.llm import LLMClient

    settings = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs"), **env}, dotenv_path=tmp_path / "none.env")
    return LLMClient(settings, sleep=sleeps if sleeps is not None else Sleeps())


def call(c, prompt, output=AlgoOut):
    from tutor.llm import ModelRef

    return c.structured(field="algorithm", prompt=prompt, variables={"problem_title": "Two Sum"},
                        output=output, run_id="run-t015", model=ModelRef.parse(MODEL))


def _objects(node):
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            yield node
        for v in node.values():
            yield from _objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from _objects(v)


# ---------------------------------------------------------------- native structured output


def test_a_call_uses_native_structured_output(tmp_path, server, prompt):
    r = call(client(tmp_path), prompt)
    assert r.output == AlgoOut(**OUTPUT)
    [req] = server.requests
    assert req["path"].endswith("/v1/messages")
    body = req["body"]
    assert body["model"] == "claude-opus-5-5"
    fmt = body["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert set(fmt["schema"]["properties"]) == {"algorithm", "confidence"}
    assert FILLED in json.dumps(body["messages"])
    assert isinstance(body.get("max_tokens"), int) and body["max_tokens"] > 0


def test_every_schema_object_is_closed(tmp_path, server, prompt):
    server.output = {"algorithm": "x", "detail": {"note": "y"}}
    call(client(tmp_path), prompt, output=Nested)
    schema = server.requests[0]["body"]["output_config"]["format"]["schema"]
    objs = list(_objects(schema))
    assert len(objs) >= 2
    assert all(o.get("additionalProperties") is False for o in objs)


def test_no_thinking_disable_and_no_sampling_parameters(tmp_path, server, prompt):
    call(client(tmp_path), prompt)
    body = server.requests[0]["body"]
    thinking = body.get("thinking")
    assert thinking is None or thinking.get("type") == "adaptive", "Opus 5.5 rejects any other thinking config"
    for p in ("temperature", "top_p", "top_k"):
        assert p not in body, f"{p} is rejected by Opus 5.5"


def test_tokens_and_cost_come_from_usage_and_pricing(tmp_path, server, prompt):
    r = call(client(tmp_path), prompt)
    assert (r.usage.input_tokens, r.usage.output_tokens) == (1500, 400)
    assert r.usage.cost_usd == pytest.approx(1500 * 4.00 / 1e6 + 400 * 20.00 / 1e6)
    [line] = [json.loads(x) for x in (tmp_path / "logs" / "llm_calls.jsonl").read_text().splitlines()]
    assert (line["provider"], line["model"], line["outcome"]) == ("anthropic", "claude-opus-5-5", "ok")


# ---------------------------------------------------------------- retries: only the client's


def test_a_server_error_is_retried_by_the_client_only(tmp_path, server, prompt):
    from tutor.llm import LLMProviderError

    sleeps = Sleeps()
    server.replies = [(500, None)] * 10
    with pytest.raises(LLMProviderError):
        call(client(tmp_path, sleeps), prompt)
    assert len(server.requests) == 4, "1 attempt + 3 client retries; the SDK's own retries must be off"
    assert len(sleeps) == 3


@pytest.mark.parametrize("status", [429, 529])
def test_rate_limit_and_overload_are_retried(tmp_path, server, prompt, status):
    server.replies = [(status, None)]
    r = call(client(tmp_path), prompt)
    assert r.attempts == 2 and len(server.requests) == 2


def test_a_timeout_is_retried(tmp_path, server, prompt):
    server.replies = [("slow", 3)]
    r = call(client(tmp_path, TUTOR__LLM__TIMEOUT_S="1"), prompt)
    assert r.attempts == 2 and len(server.requests) == 2


@pytest.mark.parametrize("status", [400, 401])
def test_a_client_error_is_not_retried(tmp_path, server, prompt, status):
    from tutor.llm import LLMProviderError

    sleeps = Sleeps()
    server.replies = [(status, None)]
    with pytest.raises(LLMProviderError) as err:
        call(client(tmp_path, sleeps), prompt)
    assert len(server.requests) == 1 and sleeps == []
    assert (err.value.status_code, err.value.retryable) == (status, False)


def test_a_refusal_is_a_provider_error_and_not_retried(tmp_path, server, prompt):
    from tutor.llm import LLMProviderError

    server.replies = [("refusal", None)]
    with pytest.raises(LLMProviderError) as err:
        call(client(tmp_path), prompt)
    assert len(server.requests) == 1
    assert err.value.retryable is False
    assert "refus" in str(err.value).lower()


# ---------------------------------------------------------------- the key


def test_the_key_comes_from_the_environment_and_is_never_logged(tmp_path, server, prompt):
    from tutor.llm import LLMProviderError

    c = client(tmp_path)
    call(c, prompt)
    server.replies = [(401, None)]
    with pytest.raises(LLMProviderError) as err:
        call(c, prompt)
    assert server.requests[0]["headers"].get("x-api-key") == KEY
    assert KEY not in str(err.value) and KEY not in repr(err.value)
    logged = "\n".join(p.read_text() for p in (tmp_path / "logs").rglob("*") if p.is_file())
    assert logged and KEY not in logged


def test_a_missing_key_is_a_config_error_before_any_request(tmp_path, server, prompt, monkeypatch):
    from tutor.llm import LLMConfigError

    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(LLMConfigError) as err:
        call(client(tmp_path), prompt)
    assert "ANTHROPIC_API_KEY" in str(err.value)
    assert server.requests == []
