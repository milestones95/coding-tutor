"""A fake OpenAI server on loopback — tester-owned (`/test write T-006`, shared from T-007).

The real `openai` SDK is pointed at it with `OPENAI_BASE_URL`, so the production adapter path runs
with no real network. It answers the Responses API (`/responses`) and Chat Completions
(`/chat/completions`) shapes, and records every request (header names lower-cased: HTTP header
names are case-insensitive).

    server = start_fake_openai(monkeypatch, key="sk-...", output={"problem_slug": "two-sum"})
    server.replies = [(429, None), ("slow", 3)]   # queued; default reply is "ok"
    server.requests                              # [{"path", "headers", "body"}]
    server.close()
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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

    def __init__(self, output: dict):
        self.output = output
        self.requests: list[dict] = []
        self.replies: list[tuple] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                # Header names are case-insensitive (RFC 9110); store them lower-cased so lookups are too.
                outer.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                                       "body": json.loads(raw or b"{}")})
                kind, arg = outer.replies.pop(0) if outer.replies else ("ok", None)
                try:
                    if kind == "slow":
                        time.sleep(arg)
                        kind = "ok"
                    if kind == "ok":
                        text = json.dumps(outer.output)
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


def start_fake_openai(monkeypatch, *, key: str, output: dict) -> FakeOpenAI:
    s = FakeOpenAI(output)
    monkeypatch.setenv("OPENAI_BASE_URL", s.url)
    monkeypatch.setenv("OPENAI_API_KEY", key)
    for proxy in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(proxy, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    return s
