"""The one LLM client wrapper (architecture §6, rule 5, D-027).

`structured()` in order:
1. Pick the model: the `model=` argument, else `llm.fields.<field>`, else `llm.default`.
2. Check everything that can be checked before spending money — a well-formed model ref, a price,
   an adapter, a key. Any gap is an `LLMConfigError` and nothing is sent.
3. Loop over attempts. Two retry budgets, counted separately (§6.4):
   - invalid output (pydantic rejects it): resend with the bad output and the validation error
     appended, up to `llm.max_output_retries` times;
   - transient provider errors (`retryable`): wait 2^k s + jitter, up to
     `llm.max_transient_retries` times.
   Anything else propagates at once.
4. Every attempt is one line in `<paths.logs>/llm_calls.jsonl` (§6.5), and the call's request
   and response bodies go to `<paths.logs>/llm_bodies/<call_id>.json`.
"""

import json
import random
import secrets
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from tutor.config import Settings
from tutor.llm.adapters import Adapter, AdapterResponse
from tutor.llm.errors import LLMConfigError, LLMOutputInvalid, LLMProviderError
from tutor.llm.messages import Message
from tutor.llm.pricing import DEFAULT_PRICING, price_for
from tutor.logs import log_event
from tutor.prompts import LoadedPrompt

T = TypeVar("T", bound=BaseModel)
PROVIDERS = ("anthropic", "openai", "gemini")

RETRY_MESSAGE = ("Your previous answer did not match the required output schema:\n{error}\n"
                 "Answer again with JSON that matches the schema exactly.")


class ModelRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: Literal["anthropic", "openai", "gemini"]
    model: str

    @classmethod
    def parse(cls, text: str) -> "ModelRef":
        """`"openai:gpt-5.5"` → ModelRef. The format `tutor.toml` and `--model` both use."""
        provider, sep, model = (text or "").partition(":")
        if not sep or not provider or not model:
            raise LLMConfigError(f"model {text!r}: expected provider:model, e.g. openai:gpt-5.5")
        if provider not in PROVIDERS:
            raise LLMConfigError(f"model {text!r}: unknown provider {provider!r} (known: {', '.join(PROVIDERS)})")
        return cls(provider=provider, model=model)

    def __str__(self) -> str:
        return f"{self.provider}:{self.model}"


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cost_usd: float


class LLMResult(BaseModel, Generic[T]):
    output: T
    call_id: str
    attempts: int
    usage: Usage          # summed over every attempt: the failed ones were paid for too (D-027)
    latency_ms: int       # the whole call, including backoff waits


def _real_adapter(provider: str) -> Adapter:
    """Adapters that exist so far. Anthropic arrives by M2, Gemini at build step 7 (D-018)."""
    if provider == "openai":
        from tutor.llm.adapters.openai import OpenAIAdapter  # deferred: only load the SDK in use

        return OpenAIAdapter()
    raise LLMConfigError(f"no adapter for provider {provider!r} yet")


def _describe(err: ValidationError) -> str:
    """Validation errors as `field: problem` lines, short enough to send back to the model."""
    lines = []
    for e in err.errors(include_url=False, include_input=False):
        loc = ".".join(str(p) for p in e["loc"]) or "(output)"
        lines.append(f"{loc}: {e['msg']}")
    return "\n".join(lines)


class LLMClient:
    def __init__(self, settings: Settings, *, adapters: Mapping[str, Adapter] | None = None,
                 pricing_path: Path | None = None, sleep: Callable[[float], None] = time.sleep):
        self._settings = settings
        self._injected = dict(adapters) if adapters is not None else None
        self._built: dict[str, Adapter] = {}
        self._pricing_path = pricing_path or DEFAULT_PRICING
        self._sleep = sleep
        self._log_path = settings.paths.logs / "llm_calls.jsonl"
        self._bodies_dir = settings.paths.logs / "llm_bodies"

    # ------------------------------------------------------------ setup checks

    def model_for(self, field: str, model: ModelRef | None = None) -> ModelRef:
        """The model a call for `field` will use: `model`, else `llm.fields.<field>`, else `llm.default`."""
        if model is not None:
            return model
        llm = self._settings.llm
        return ModelRef.parse(llm.fields.get(field) or llm.default)

    def _adapter(self, provider: str) -> Adapter:
        if self._injected is not None:
            if provider not in self._injected:
                raise LLMConfigError(f"no adapter for provider {provider!r}")
            return self._injected[provider]
        if provider not in self._built:
            self._built[provider] = _real_adapter(provider)
        return self._built[provider]

    # ------------------------------------------------------------ the call

    def structured(self, *, field: str, prompt: LoadedPrompt, variables: dict[str, str],
                   output: type[T], run_id: str, model: ModelRef | None = None) -> LLMResult[T]:
        ref = self.model_for(field, model)
        price = price_for(self._pricing_path, str(ref))
        adapter = self._adapter(ref.provider)
        cfg = self._settings.llm

        messages = [Message(role="user", content=prompt.substitute(variables))]
        schema = output.model_json_schema()
        call_id = secrets.token_hex(8)
        common = {"call_id": call_id, "kind": "structured", "field": field, "prompt_name": prompt.name,
                  "prompt_version": prompt.version, "prompt_sha256": prompt.sha256,
                  "provider": ref.provider, "model": ref.model}
        bodies: list[dict] = []
        totals = Usage(input_tokens=0, output_tokens=0, cost_usd=0.0)
        output_retries = transient_retries = attempt = 0
        call_start = time.monotonic()

        while True:
            attempt += 1
            started = time.monotonic()
            try:
                resp: AdapterResponse = adapter.structured(model=ref.model, messages=list(messages), schema=schema,
                                                           schema_name=output.__name__, timeout_s=float(cfg.timeout_s))
            except LLMProviderError as e:
                self._log(run_id, common, attempt, started, 0, 0, 0.0, "provider_error", str(e))
                bodies.append({"attempt": attempt, "request": {"model": ref.model,
                               "messages": [m.model_dump() for m in messages]}, "error": str(e)})
                self._write_bodies(call_id, bodies)
                if e.retryable and transient_retries < cfg.max_transient_retries:
                    transient_retries += 1
                    self._sleep(2 ** transient_retries + random.random())
                    continue
                raise

            cost = price.cost(resp.input_tokens, resp.output_tokens)
            totals = Usage(input_tokens=totals.input_tokens + resp.input_tokens,
                           output_tokens=totals.output_tokens + resp.output_tokens,
                           cost_usd=totals.cost_usd + cost)
            bodies.append({"attempt": attempt, "request": resp.request, "response": resp.response})
            self._write_bodies(call_id, bodies)
            try:
                parsed = output.model_validate_json(resp.text)
            except ValidationError as e:
                error = _describe(e)
                self._log(run_id, common, attempt, started, resp.input_tokens, resp.output_tokens, cost,
                          "invalid_output", error)
                if output_retries < cfg.max_output_retries:
                    output_retries += 1
                    messages = messages + [Message(role="assistant", content=resp.text),
                                           Message(role="user", content=RETRY_MESSAGE.format(error=error))]
                    continue
                raise LLMOutputInvalid(f"{field}: output still invalid after {attempt} attempts:\n{error}") from None

            self._log(run_id, common, attempt, started, resp.input_tokens, resp.output_tokens, cost, "ok", None)
            return LLMResult(output=parsed, call_id=call_id, attempts=attempt, usage=totals,
                             latency_ms=int((time.monotonic() - call_start) * 1000))

    # ------------------------------------------------------------ logging

    def _log(self, run_id, common, attempt, started, input_tokens, output_tokens, cost, outcome, error):
        log_event("llm_call", run_id=run_id, path=self._log_path, **common, attempt=attempt,
                  input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost,
                  latency_ms=int((time.monotonic() - started) * 1000), outcome=outcome, error=error)

    def _write_bodies(self, call_id: str, attempts: list[dict]) -> None:
        self._bodies_dir.mkdir(parents=True, exist_ok=True)
        path = self._bodies_dir / f"{call_id}.json"
        path.write_text(json.dumps({"call_id": call_id, "exchanges": attempts}, indent=2, default=str,
                                   ensure_ascii=False))
