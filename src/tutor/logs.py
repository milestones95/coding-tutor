"""Structured JSON-lines logs (architecture §13).

One JSON object per line, appended, so a run can be replayed or grepped later. Every line has
`ts` (UTC, ISO-8601), `run_id` and `event`; callers add whatever fields the event needs.
"""

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RESERVED = frozenset({"ts", "run_id", "event"})


def new_run_id() -> str:
    """A run id that sorts by start time and is unique: `20261102T231500Z-1a2b3c4d`."""
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"


def log_event(event: str, *, run_id: str, path: Path | None = None, **fields: Any) -> None:
    """Append one event to `path` (default `<paths.logs>/pipeline.jsonl`).

    `ts`, `run_id` and `event` are set here and can't be overridden by `fields`, so every line
    is guaranteed to carry them. Values that aren't JSON types (paths, dates) are written as str.
    """
    clash = RESERVED & fields.keys()
    if clash:
        raise ValueError(f"reserved log fields can't be passed as extra fields: {sorted(clash)}")
    if path is None:
        from tutor.config import load_settings  # deferred: logging must not require config at import

        path = load_settings().paths.logs / "pipeline.jsonl"
    record = {"ts": datetime.now(UTC).isoformat(timespec="milliseconds"), "run_id": run_id, "event": event, **fields}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
