"""Provider-neutral message types (architecture §6.2).

Adapters translate these to and from their SDK's format, so nothing above `tutor/llm/adapters/`
ever sees an SDK type. `ToolCall` and `ToolSpec` belong to the same contract; they are used by
`chat()` in M5.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ToolCall(_Model):
    id: str
    name: str
    arguments: dict


class ToolSpec(_Model):
    name: str
    description: str
    parameters: dict  # JSON Schema


class Message(_Model):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list[ToolCall] = []      # assistant only
    tool_call_id: str | None = None      # tool only
    is_error: bool = False               # tool only
