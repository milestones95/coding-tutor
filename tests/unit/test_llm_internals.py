"""Builder unit tests for tutor.llm internals (T-006). No network: SDK errors are built by hand."""

import json
from enum import StrEnum

import httpx2 as httpx  # the HTTP library openai 3.x is built on
import openai
import pytest
from pydantic import BaseModel

from _llm_fake import FakeAdapter
from tutor.config import load_settings
from tutor.llm import LLMClient, LLMConfigError, LLMProviderError
from tutor.llm.adapters.openai import OpenAIAdapter, strict_schema
from tutor.llm.pricing import Price, load_pricing
from tutor.prompts import load_prompt


class Kind(StrEnum):
    a = "a"
    b = "b"


class Inner(BaseModel):
    name: str
    note: str | None = None


class Outer(BaseModel):
    kind: Kind
    items: list[Inner]
    best: Inner
    score: float = 0.5


# ---------------------------------------------------------------- strict schema


def _objects(node):
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            yield node
        for v in node.values():
            yield from _objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from _objects(v)


def test_strict_schema_closes_every_object_and_requires_every_property():
    out = strict_schema(Outer.model_json_schema())
    objs = list(_objects(out))
    assert len(objs) >= 2  # Outer and Inner (in $defs)
    for o in objs:
        assert o["additionalProperties"] is False
        assert o["required"] == list(o["properties"])


def test_strict_schema_drops_defaults_and_leaves_the_input_alone():
    src = Outer.model_json_schema()
    before = json.dumps(src, sort_keys=True)
    out = strict_schema(src)
    assert '"default"' not in json.dumps(out)
    assert json.dumps(src, sort_keys=True) == before


def test_strict_schema_keeps_a_property_named_default():
    class P(BaseModel):
        default: str

    out = strict_schema(P.model_json_schema())
    assert "default" in out["properties"] and out["required"] == ["default"]


def test_a_ref_with_siblings_is_inlined():
    schema = {"type": "object", "properties": {"x": {"$ref": "#/$defs/I", "description": "d"}},
              "$defs": {"I": {"type": "object", "properties": {"n": {"type": "string"}}}}}
    x = strict_schema(schema)["properties"]["x"]
    assert "$ref" not in x and x["description"] == "d" and x["required"] == ["n"]


# ---------------------------------------------------------------- pricing


def test_price_cost_is_per_million_tokens():
    assert Price(5.0, 30.0, "2026-11-03").cost(1_000_000, 100_000) == pytest.approx(8.0)


def test_a_pricing_entry_missing_a_field_is_a_config_error(tmp_path):
    p = tmp_path / "p.toml"
    p.write_text('[models."openai:x"]\ninput_per_mtok = 1.0\n')
    with pytest.raises(LLMConfigError, match="openai:x"):
        load_pricing(p)


def test_the_repo_pricing_file_parses():
    assert "openai:gpt-5.5" in load_pricing(__import__("tutor.llm.pricing", fromlist=["x"]).DEFAULT_PRICING)


# ---------------------------------------------------------------- OpenAI error mapping


def _adapter(monkeypatch, key="sk-unit-test-key"):
    monkeypatch.setenv("OPENAI_API_KEY", key)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9/v1")
    return OpenAIAdapter()


def _status_error(status, message):
    req = httpx.Request("POST", "http://127.0.0.1:9/v1/responses")
    return openai.APIStatusError(message, response=httpx.Response(status, request=req), body=None)


@pytest.mark.parametrize("status,retryable", [(429, True), (500, True), (503, True), (400, False), (401, False), (404, False)])
def test_status_errors_are_classified(monkeypatch, status, retryable):
    a = _adapter(monkeypatch)

    def boom(**kw):
        raise _status_error(status, "nope")

    monkeypatch.setattr(a._client.responses, "create", boom)
    with pytest.raises(LLMProviderError) as err:
        a.structured(model="m", messages=[], schema={"type": "object", "properties": {}}, schema_name="O", timeout_s=1)
    assert (err.value.status_code, err.value.retryable) == (status, retryable)


def test_connection_errors_are_retryable(monkeypatch):
    a = _adapter(monkeypatch)

    def boom(**kw):
        raise openai.APITimeoutError(request=httpx.Request("POST", "http://127.0.0.1:9/v1/responses"))

    monkeypatch.setattr(a._client.responses, "create", boom)
    with pytest.raises(LLMProviderError) as err:
        a.structured(model="m", messages=[], schema={"type": "object", "properties": {}}, schema_name="O", timeout_s=1)
    assert err.value.retryable is True and err.value.status_code is None


def test_a_key_quoted_in_a_provider_error_is_scrubbed(monkeypatch):
    a = _adapter(monkeypatch, key="sk-secret-quoted-back")

    def boom(**kw):
        raise _status_error(401, "Incorrect API key provided: sk-secret-quoted-back")

    monkeypatch.setattr(a._client.responses, "create", boom)
    with pytest.raises(LLMProviderError) as err:
        a.structured(model="m", messages=[], schema={"type": "object", "properties": {}}, schema_name="O", timeout_s=1)
    assert "sk-secret-quoted-back" not in str(err.value) and "***" in str(err.value)


# ---------------------------------------------------------------- body file


def test_the_body_file_keeps_every_attempt(tmp_path):
    (tmp_path / "p" / "demo").mkdir(parents=True)
    (tmp_path / "p" / "demo" / "v1.md").write_text("---\nname: demo\nversion: v1\nvariables: []\n---\nSay hi.\n")
    settings = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")
    fake = FakeAdapter([LLMProviderError("down", retryable=True, status_code=503), "not json", {"name": "x"}])
    client = LLMClient(settings, adapters={"openai": fake}, sleep=lambda s: None)
    r = client.structured(field="f", prompt=load_prompt("demo", "v1", root=tmp_path / "p"), variables={},
                          output=Inner, run_id="r")
    body = json.loads((tmp_path / "logs" / "llm_bodies" / f"{r.call_id}.json").read_text())
    assert [a["attempt"] for a in body["exchanges"]] == [1, 2, 3]
    assert "error" in body["exchanges"][0] and body["exchanges"][2]["response"] == {"text": '{"name": "x"}'}
