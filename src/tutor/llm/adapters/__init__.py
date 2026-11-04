"""The adapter interface (D-027). Only modules in this package may import a provider SDK (§4.3 #2).

An adapter does one thing: translate a provider-neutral request into one SDK call and the
answer back. Retries, validation, cost and logging all live in the client, so every provider
gets them the same way.
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from tutor.llm.messages import Message


class AdapterResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str             # the raw output text; the client validates it
    input_tokens: int
    output_tokens: int
    request: dict         # what was sent, minus credentials — kept in llm_bodies/ for debugging
    response: dict        # what came back


class Adapter(Protocol):
    def structured(self, *, model: str, messages: list[Message], schema: dict, schema_name: str,
                   timeout_s: float) -> AdapterResponse:
        """One request. Raises `LLMProviderError` (with `retryable`) on any provider failure."""
        ...
