"""Contract: the real OpenAI adapter, against a fake OpenAI server on loopback — architecture §6.1,
§6.4, §6.5, §11; rule 5; D-027. Tester-owned (`/test write T-006`, 2026-11-03).

The client is built with no injected adapters, so the production path runs: `LLMClient` → the
real `adapters/openai.py` → the real `openai` SDK → HTTP. The SDK's default `OPENAI_BASE_URL`
env var points it at a tiny server in this process. No real network is used (the conftest
blocks it); loopback is allowed.

What this protects:
- Native structured output: the request asks for JSON matching the output schema, strictly.
  Either the Responses API (`/responses`, `text.format`) or Chat Completions
  (`/chat/completions`, `response_format`) is accepted.
- The client's retry table is the only retry logic: the SDK's own hidden retries are off, so a
  failing server sees exactly 1 + `llm.max_transient_retries` requests.
- 429, 5xx and timeouts are retryable; other 4xx are not.
- The API key comes from the environment, and is never written to a log, a body file or an
  error message.
- A missing key is an `LLMConfigError` before any request.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from pydantic import BaseModel

KEY = "sk-SENTINEL-t006-must-never-be-logged-5c1e"
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


class AlgoOut(BaseModel):
    algorithm: str
    confidence: float


# ---------------------------------------------------------------- the fake OpenAI server


def _responses_body(text):
    return {
        "id": "resp_t006", "object": "response", "created_at": 0, "status": "completed", "model": "gpt-5.5",
        "output": [{"type": "message", "id": "msg_t006", "status": "completed", "role": "assistant",
                    "content": [{"type": "output_text", "text": text, "annotations": []}]}],
        "parallel_tool_calls": False, "tool_choice": "auto", "tools": [],
        "usage": {"input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500,
                  "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}},
    }


def _chat_body(text):
    return {
        "id": "chatcmpl-t006", "object": "chat.completion", "created": 0, "model": "gpt-5.5",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": text, "refusal": None}}],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 300, "total_tokens": 1500},
    }


class FakeOpenAI:
    """Replies are queued as ("ok", None) | (status_code, None) | ("slow", seconds); default "ok"."""

    def __init__(self):
        self.requests: list[dict] = []
        self.replies: list[tuple] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                outer.requests.append({"path": self.path, "headers": dict(self.headers),
                                       "body": json.loads(raw or b"{}")})
                kind, arg = outer.replies.pop(0) if outer.replies else ("ok", None)
                try:
                    if kind == "slow":
                        time.sleep(arg)
                        kind = "ok"
                    if kind == "ok":
                        text = json.dumps(OUTPUT)
                        body = _chat_body(text) if self.path.endswith("/chat/completions") else _responses_body(text)
                        self._send(200, body)
                    else:
                        self._send(kind, {"error": {"message": f"simulated {kind}", "type": "simulated",
                                                    "param": None, "code": None}})
                except (BrokenPipeError, ConnectionResetError):
                    pass  # the client gave up (timeout test)

            def _send(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def server(monkeypatch):
    s = FakeOpenAI()
    monkeypatch.setenv("OPENAI_BASE_URL", s.url)
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    for proxy in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(proxy, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
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

    settings = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs"), **env},
                             dotenv_path=tmp_path / "none.env")
    return LLMClient(settings, sleep=sleeps if sleeps is not None else Sleeps())  # real adapters, real pricing


def call(c, prompt):
    return c.structured(field="algorithm", prompt=prompt, variables={"problem_title": "Two Sum"},
                        output=AlgoOut, run_id="run-t006-contract")


def _format(body):
    """The structured-output request block, wherever the chosen API puts it."""
    if "text" in body and isinstance(body["text"], dict) and "format" in body["text"]:
        f = body["text"]["format"]
        return f["type"], f.get("strict"), f.get("schema")
    rf = body.get("response_format") or {}
    js = rf.get("json_schema") or {}
    return rf.get("type"), js.get("strict"), js.get("schema")


def _everything_logged(tmp_path):
    logs = tmp_path / "logs"
    return "\n".join(p.read_text() for p in logs.rglob("*") if p.is_file()) if logs.exists() else ""


# ---------------------------------------------------------------- native structured output


def test_a_call_uses_native_structured_output(tmp_path, server, prompt):
    r = call(client(tmp_path), prompt)
    assert r.output == AlgoOut(**OUTPUT)
    [req] = server.requests
    assert req["path"].endswith(("/responses", "/chat/completions")), req["path"]
    assert req["body"]["model"] == "gpt-5.5"
    kind, strict, schema = _format(req["body"])
    assert kind == "json_schema", "OpenAI's native structured output, not free text + parsing"
    assert strict is True
    assert set(schema["properties"]) == {"algorithm", "confidence"}
    assert FILLED in json.dumps(req["body"]), "the filled prompt is sent"


def test_tokens_and_cost_come_from_the_response_and_pricing_toml(tmp_path, server, prompt):
    r = call(client(tmp_path), prompt)
    assert (r.usage.input_tokens, r.usage.output_tokens) == (1200, 300)
    # config/pricing.toml: $5.00 in, $30.00 out per 1M tokens
    assert r.usage.cost_usd == pytest.approx(1200 * 5.00 / 1e6 + 300 * 30.00 / 1e6)
    [line] = [json.loads(x) for x in (tmp_path / "logs" / "llm_calls.jsonl").read_text().splitlines()]
    assert (line["provider"], line["model"], line["outcome"]) == ("openai", "gpt-5.5", "ok")
    assert (line["input_tokens"], line["output_tokens"]) == (1200, 300)


# ---------------------------------------------------------------- retries: only the client's


def test_a_server_error_is_retried_by_the_client_only(tmp_path, server, prompt):
    from tutor.llm import LLMProviderError

    sleeps = Sleeps()
    server.replies = [(500, None)] * 10
    with pytest.raises(LLMProviderError):
        call(client(tmp_path, sleeps), prompt)
    assert len(server.requests) == 4, "1 attempt + 3 client retries; the SDK's own retries must be off"
    assert len(sleeps) == 3


def test_a_rate_limit_is_retried(tmp_path, server, prompt):
    server.replies = [(429, None)]
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
    assert err.value.status_code == status
    assert err.value.retryable is False


# ---------------------------------------------------------------- the key


def test_the_key_comes_from_the_environment_and_is_never_logged(tmp_path, server, prompt):
    from tutor.llm import LLMProviderError

    c = client(tmp_path)
    call(c, prompt)
    server.replies = [(401, None)]
    with pytest.raises(LLMProviderError) as err:
        call(c, prompt)
    assert server.requests[0]["headers"].get("Authorization") == f"Bearer {KEY}"
    assert KEY not in str(err.value) and KEY not in repr(err.value)
    logged = _everything_logged(tmp_path)
    assert "llm_calls.jsonl" in str(list((tmp_path / "logs").rglob("*"))) and logged
    assert KEY not in logged, "the API key must never reach llm_calls.jsonl or llm_bodies/"


def test_a_missing_key_is_a_config_error_before_any_request(tmp_path, server, prompt, monkeypatch):
    from tutor.llm import LLMConfigError

    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(LLMConfigError) as err:
        call(client(tmp_path), prompt)
    assert "OPENAI_API_KEY" in str(err.value)
    assert server.requests == []


def test_a_provider_with_no_adapter_yet_is_a_config_error_before_any_request(tmp_path, server, prompt):
    from tutor.llm import LLMConfigError

    with pytest.raises(LLMConfigError):
        call(client(tmp_path, TUTOR__LLM__DEFAULT="gemini:gemini-x"), prompt)
    assert server.requests == []
