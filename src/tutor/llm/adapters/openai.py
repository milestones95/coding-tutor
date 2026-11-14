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

import os
import re

import openai
from openai.types.responses import EasyInputMessageParam, ResponseTextConfigParam

from tutor.llm.adapters import AdapterResponse
from tutor.llm.adapters.schema import strict_schema  # re-exported: shared with the Anthropic adapter
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
        # Typed with the SDK's own request types, so the type checker catches a malformed request.
        input_items = [_input_item(m) for m in messages]
        text: ResponseTextConfigParam = {"format": {"type": "json_schema", "name": _schema_name(schema_name),
                                                    "schema": strict_schema(schema), "strict": True}}
        request = {"model": model, "input": input_items, "text": text, "store": False}  # kept in llm_bodies/
        try:
            resp = self._client.responses.create(model=model, input=list(input_items), text=text, store=False,
                                                 timeout=timeout_s)
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


def _input_item(m: Message) -> EasyInputMessageParam:
    # structured() only sends user/assistant/system text. Tool messages belong to chat() (M5).
    if m.role == "tool":
        raise ValueError("a tool message can't be sent through structured()")
    return {"role": m.role, "content": m.content}


def _schema_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)[:64] or "output"
