"""Settings: `tutor.toml` + `TUTOR__SECTION__KEY` env overrides → one frozen object (architecture §11).

Shape decisions:
- Defaults live only in `tutor.toml`. The models below have no defaults for keys the file must
  hold, so a missing key fails loudly instead of silently using a second, drifting default.
  Only keys the architecture says are "unset" by default are optional.
- `extra="forbid"` everywhere: an unknown key in the file or the env is a `ConfigError`. This
  is also what keeps secrets out — there is no field an API key could land in.
- Secrets never enter `Settings`. `.env` is loaded into `os.environ` (never overriding what the
  shell already set) so provider adapters can read their keys from the environment.
- Error messages name the key and the problem, never the value, so a mistyped secret is not
  echoed into logs.
"""

import os
import tomllib
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PREFIX = "TUTOR__"


class ConfigError(Exception):
    """Invalid configuration. The message names the offending key(s), never their values."""


class _Section(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Paths(_Section):
    capture_db: Path
    eval_capture_db: Path
    analysis_db: Path
    fixture_db: Path
    verdicts: Path
    logs: Path

    @field_validator("*")
    @classmethod
    def _repo_relative(cls, v: Path) -> Path:
        return v if v.is_absolute() else REPO_ROOT / v


class Capture(_Section):
    submits_reliable_since: date | None = None


class Time(_Section):
    timezone: str


class Condenser(_Section):
    interval_s: int
    error_max_chars: int
    token_budget: int
    rewrite_threshold: float


class LLM(_Section):
    default: str
    generator: str
    fields: dict[str, str] = {}
    judge: str | None = None
    max_output_retries: int
    max_transient_retries: int
    timeout_s: int


class Agent(_Section):
    max_steps: int


class Sql(_Section):
    timeout_s: int
    max_rows: int


class Settings(_Section):
    paths: Paths
    capture: Capture = Capture()
    time: Time
    condenser: Condenser
    llm: LLM
    prompts: dict[str, str] = {}
    agent: Agent
    sql: Sql


def _apply_env(raw: dict[str, Any], env: Mapping[str, str]) -> None:
    """Merge TUTOR__A__B[__C]=value into the raw TOML dict (keys lower-cased)."""
    for name, value in env.items():
        if not name.startswith(ENV_PREFIX):
            continue
        parts = [p.lower() for p in name[len(ENV_PREFIX):].split("__")]
        if len(parts) < 2 or not all(parts):
            raise ConfigError(f"{name}: expected {ENV_PREFIX}SECTION__KEY")
        node = raw
        for part in parts[:-1]:
            child = node.setdefault(part, {})
            if not isinstance(child, dict):
                raise ConfigError(f"{'.'.join(parts)}: {part} is not a section")
            node = child
        node[parts[-1]] = value


def _describe(err: ValidationError) -> str:
    lines = []
    for e in err.errors(include_input=False, include_url=False):
        key = ".".join(str(p) for p in e["loc"])
        problem = "unknown key" if e["type"] == "extra_forbidden" else e["msg"]
        lines.append(f"{key}: {problem}")
    return "invalid configuration — " + "; ".join(lines)


def load_settings(
    toml_path: Path | None = None,
    env: Mapping[str, str] | None = None,
    dotenv_path: Path | None = None,
) -> Settings:
    """Load `tutor.toml`, apply `TUTOR__…` overrides, and validate.

    `env` defaults to the process environment, read after `.env` is loaded. Pass an explicit
    mapping (tests do) to control overrides without touching `os.environ`.
    """
    dotenv_path = dotenv_path if dotenv_path is not None else REPO_ROOT / ".env"
    if dotenv_path.is_file():
        load_dotenv(dotenv_path, override=False)

    toml_path = toml_path if toml_path is not None else REPO_ROOT / "tutor.toml"
    try:
        raw = tomllib.loads(toml_path.read_text())
    except FileNotFoundError as e:
        raise ConfigError(f"config file not found: {toml_path}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{toml_path}: not valid TOML ({e})") from e

    _apply_env(raw, os.environ if env is None else env)
    try:
        return Settings.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(_describe(e)) from None
