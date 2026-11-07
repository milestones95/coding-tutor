"""A fake Anthropic Messages API on loopback — tester-owned (`/test write T-015`, 2026-11-07).

The real `anthropic` SDK is pointed at it with `ANTHROPIC_BASE_URL`, so the production adapter
runs with no real network. Response bodies follow the Messages API: Opus 5.5 always thinks, so a
successful reply carries a (display-omitted, empty) `thinking` block before the `text` block that
holds the structured-output JSON. Every request is recorded with lower-cased header names.

    server = start_fake_anthropic(monkeypatch, key="sk-ant-...", output={"a": 1})
    server.replies = [(429, None), ("slow", 3), ("refusal", None)]   # queued; default reply "ok"
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ERROR_TYPES = {400: "invalid_request_error", 401: "authentication_error", 403: "permission_error",
               404: "not_found_error", 429: "rate_limit_error", 500: "api_error", 529: "overloaded_error"}


def _message(content, stop_reason, model):
    return {"id": "msg_fake_t015", "type": "message", "role": "assistant", "model": model,
            "content": content, "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 1500, "output_tokens": 400}}


class FakeAnthropic:
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
                body = json.loads(raw or b"{}")
                outer.requests.append({"path": self.path, "body": body,
                                       "headers": {k.lower(): v for k, v in self.headers.items()}})
                kind, arg = outer.replies.pop(0) if outer.replies else ("ok", None)
                model = body.get("model", "claude-opus-5-5")
                try:
                    if kind == "slow":
                        time.sleep(arg)
                        kind = "ok"
                    if kind == "ok":
                        self._send(200, _message([{"type": "thinking", "thinking": "", "signature": "sig_fake"},
                                                  {"type": "text", "text": json.dumps(outer.output)}],
                                                 "end_turn", model))
                    elif kind == "refusal":
                        msg = _message([], "refusal", model)
                        msg["stop_details"] = {"type": "refusal", "category": None, "explanation": None}
                        self._send(200, msg)
                    else:
                        self._send(kind, {"type": "error", "error": {"type": ERROR_TYPES.get(kind, "api_error"),
                                                                     "message": f"simulated {kind}"}})
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _send(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def start_fake_anthropic(monkeypatch, *, key: str, output: dict) -> FakeAnthropic:
    s = FakeAnthropic(output)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", s.url)
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    for var in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    return s
