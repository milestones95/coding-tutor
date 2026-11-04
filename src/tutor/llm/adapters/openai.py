"""OpenAI adapter: the Responses API with native structured output (D-018, D-027).

- The output schema goes in `text.format` as a strict `json_schema`, so the model is
  constrained to it. The client still validates with pydantic.
- `max_retries=0`: the SDK retries 429/5xx on its own by default, which would hide attempts
  from the log and multiply the client's retry table. The client is the only one that retries.
- The key comes from `OPENAI_API_KEY` (loaded from `.env` by config). The base URL is the SDK's
  default, which honours `OPENAI_BASE_URL` (the contract tests point it at a local server).
- `store=False`: OpenAI doesn't keep the session code; the request/response are already in
  `logs/llm_bodies/`.
"""

import copy
import os
import re

import openai

from tutor.llm.adapters import AdapterResponse
from tutor.llm.errors import LLMConfigError, LLMProviderError
from tutor.llm.messages import Message

KEY_ENV = "OPENAI_API_KEY"


class OpenAIAdapter:
    def __init__(self) -> None:
        key = os.environ.get(KEY_ENV)
        if not key:
            raise LLMConfigError(f"{KEY_ENV} is not set; put it in .env to use an openai: model")
        self._key = key
        self._client = openai.OpenAI(api_key=key, max_retries=0)

    def structured(self, *, model: str, messages: list[Message], schema: dict, schema_name: str,
                   timeout_s: float) -> AdapterResponse:
        request = {
            "model": model,
            "input": [{"role": m.role, "content": m.content} for m in messages],
            "text": {"format": {"type": "json_schema", "name": _schema_name(schema_name),
                                "schema": strict_schema(schema), "strict": True}},
            "store": False,
        }
        try:
            resp = self._client.responses.create(**request, timeout=timeout_s)
        except openai.APIStatusError as e:
            status = e.status_code
            raise LLMProviderError(self._scrub(f"OpenAI HTTP {status}: {e.message}"),
                                   retryable=status == 429 or status >= 500, status_code=status) from None
        except openai.APIConnectionError as e:  # includes APITimeoutError
            raise LLMProviderError(f"OpenAI {type(e).__name__}: {e}", retryable=True) from None
        usage = resp.usage
        return AdapterResponse(
            text=resp.output_text or "",
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            request=request,
            response=resp.model_dump(mode="json"),
        )

    def _scrub(self, text: str) -> str:
        """Provider error messages can quote the key back; never let it travel further."""
        return text.replace(self._key, "***")


def _schema_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)[:64] or "output"


def strict_schema(schema: dict) -> dict:
    """Rewrite a pydantic JSON schema into the form OpenAI's strict mode accepts.

    OpenAI's documented strict-mode rules: every object sets `additionalProperties: false` and
    lists all of its properties in `required`. `default` is dropped (with every field required
    it means nothing), and a `$ref` that has sibling keys is inlined, because strict mode
    rejects siblings next to `$ref`. The input is not modified.
    """
    root = copy.deepcopy(schema)
    defs = root.get("$defs", {})

    def walk(node):
        if isinstance(node, list):
            return [walk(n) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node and len(node) > 1:
            target = defs.get(node["$ref"].rsplit("/", 1)[-1], {})
            node = {**copy.deepcopy(target), **{k: v for k, v in node.items() if k != "$ref"}}
        node.pop("default", None)
        out = {}
        for k, v in node.items():
            if k in ("properties", "$defs", "definitions"):
                out[k] = {name: walk(sub) for name, sub in v.items()}
            else:
                out[k] = walk(v)
        if out.get("type") == "object" or "properties" in out:
            out["additionalProperties"] = False
            out["required"] = list(out.get("properties", {}))
        return out

    return walk(root)
