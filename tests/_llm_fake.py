"""Scripted stand-in for a provider adapter — tester-owned (`/test write T-006`, 2026-11-03).

The client (`tutor.llm.LLMClient`) is judged against this fake, so the builder doesn't write the
thing that grades its own retry and logging logic (rule 11). The builder's unit tests may import
it too. It implements the adapter interface pinned in D-027:

    adapter.structured(*, model: str, messages: list[Message], schema: dict, schema_name: str,
                       timeout_s: float) -> tutor.llm.adapters.AdapterResponse

Each script item is played once per call, in order:
    str            -> the provider's raw output text
    dict / list    -> JSON-encoded, then as str
    BaseException  -> raised (e.g. LLMProviderError(..., retryable=True))
    AdapterResponse-> returned as is
"""

import json


class FakeAdapter:
    def __init__(self, script, *, input_tokens: int = 1000, output_tokens: int = 500):
        self.script = list(script)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.calls: list[dict] = []

    def structured(self, **kw):
        from tutor.llm.adapters import AdapterResponse

        self.calls.append(kw)
        if not self.script:
            raise AssertionError(f"FakeAdapter: script exhausted after {len(self.calls) - 1} call(s)")
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, (dict, list)):
            item = json.dumps(item)
        if isinstance(item, str):
            return AdapterResponse(
                text=item,
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                request={"model": kw.get("model"), "messages": [m.model_dump() for m in kw.get("messages", [])]},
                response={"text": item},
            )
        return item
