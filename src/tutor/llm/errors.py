"""Error types for the LLM layer (architecture §6.4, D-027).

All three share `LLMError`, so a caller that only wants "the LLM part failed" catches one type.
Messages name models, providers and env var names, never key values.
"""


class LLMError(Exception):
    """Base class for every error raised by `tutor.llm`."""


class LLMConfigError(LLMError):
    """Unknown model, missing key or missing price. Raised before any request is sent."""


class LLMOutputInvalid(LLMError):
    """The output still failed schema validation after the allowed retries."""


class LLMProviderError(LLMError):
    """The provider failed. Adapters raise it; the client retries only when `retryable`.

    `retryable` is the adapter's call because only it knows its SDK's exceptions: 429, 5xx,
    timeouts and dropped connections are transient; other 4xx (bad request, auth) are not.
    """

    def __init__(self, message: str, *, retryable: bool, status_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
