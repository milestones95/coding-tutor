"""Anthropic adapter: the Messages API with native structured output (D-018, D-027, T-015).

- The output schema goes in `output_config.format` as a `json_schema`, so the model is constrained
  to it. The client still validates with pydantic (and retries an invalid answer), so constraints
  the API's schema subset doesn't take (lengths, ranges, item counts) are dropped here and enforced
  there.
- Opus 5.5 always thinks and rejects a thinking-disable or sampling parameters (`temperature`,
  `top_p`, `top_k`), so none are sent. The reply's first block is `thinking`; the JSON is the first
  `text` block.
- `max_retries=0`: as with OpenAI, the client is the only one that retries (429 / 5xx / timeouts).
- A refusal (`stop_reason == "refusal"`) is a non-retryable `LLMProviderError` (D-047): asking again
  with the same input gets the same answer and costs money.
- The key comes from `ANTHROPIC_API_KEY` (loaded from `.env` by config). The base URL is the SDK's
  default, which honours `ANTHROPIC_BASE_URL` (the contract tests point it at a local server).
"""

import os

import anthropic

from tutor.llm.adapters import AdapterResponse
from tutor.llm.adapters.schema import strict_schema
from tutor.llm.errors import LLMConfigError, LLMProviderError
from tutor.llm.messages import Message

KEY_ENV = "ANTHROPIC_API_KEY"
# Thinking shares this budget with the answer. The Part 1 answers are a few hundred tokens; the
# rest is room to think. Only output actually produced is billed.
MAX_TOKENS = 16000
# JSON-schema keywords the structured-output subset doesn't accept; pydantic still checks them.
UNSUPPORTED = ("minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
               "multipleOf", "minItems", "maxItems", "pattern", "format", "title")


class AnthropicAdapter:
    def __init__(self) -> None:
        key = os.environ.get(KEY_ENV)
        if not key:
            raise LLMConfigError(f"{KEY_ENV} is not set; put it in .env to use an anthropic: model")
        self._key = key
        self._client = anthropic.Anthropic(api_key=key, max_retries=0)

    def structured(self, *, model: str, messages: list[Message], schema: dict, schema_name: str,
                   timeout_s: float) -> AdapterResponse:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        turns = [_turn(m) for m in messages if m.role != "system"]
        output_config = {"format": {"type": "json_schema", "schema": closed_schema(schema)}}
        request: dict = {"model": model, "max_tokens": MAX_TOKENS, "messages": turns, "output_config": output_config}
        if system:
            request["system"] = system
        try:
            resp = self._client.messages.create(**request, timeout=timeout_s)
        except anthropic.APIStatusError as e:
            status = e.status_code
            raise LLMProviderError(self._scrub(f"Anthropic HTTP {status}: {e.message}"),
                                   retryable=status == 429 or status >= 500, status_code=status) from None
        except anthropic.APIConnectionError as e:  # includes APITimeoutError
            raise LLMProviderError(f"Anthropic {type(e).__name__}: {e}", retryable=True) from None
        if resp.stop_reason == "refusal":
            raise LLMProviderError("Anthropic refused the request (stop_reason: refusal)", retryable=False)
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return AdapterResponse(
            text=text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            request=request,
            response=resp.model_dump(mode="json"),
        )

    def _scrub(self, text: str) -> str:
        """Provider error messages can quote the key back; never let it travel further."""
        return text.replace(self._key, "***")


def _turn(m: Message) -> dict:
    # structured() only sends user/assistant text. Tool messages belong to chat() (M5).
    if m.role == "tool":
        raise ValueError("a tool message can't be sent through structured()")
    return {"role": m.role, "content": m.content}


def closed_schema(schema: dict) -> dict:
    """Every object closed and fully required (the same rewrite as OpenAI's strict mode), minus the
    keywords the structured-output subset rejects. The input is not modified."""

    def strip(node):
        if isinstance(node, list):
            return [strip(n) for n in node]
        if not isinstance(node, dict):
            return node
        out = {}
        for k, v in node.items():
            if k in ("properties", "$defs", "definitions"):
                out[k] = {name: strip(sub) for name, sub in v.items()}
            elif k not in UNSUPPORTED:
                out[k] = strip(v)
        return out

    return strip(strict_schema(schema))
