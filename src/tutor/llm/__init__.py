"""The LLM layer: one client wrapper, provider adapters, pricing (architecture §6, rule 5).

Everything else in `tutor` calls an LLM only through `LLMClient`.
"""

from tutor.llm.client import LLMClient, LLMResult, ModelRef, Usage
from tutor.llm.errors import LLMConfigError, LLMError, LLMOutputInvalid, LLMProviderError

__all__ = ["LLMClient", "LLMResult", "ModelRef", "Usage",
           "LLMError", "LLMConfigError", "LLMOutputInvalid", "LLMProviderError"]
