"""Builder unit tests for tutor.logs internals (T-003)."""

import json
import re
from datetime import date
from pathlib import Path

import pytest

from tutor.logs import log_event, new_run_id


def test_run_id_format_sorts_by_time():
    assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", new_run_id())


def test_ts_cannot_be_overridden(tmp_path):
    with pytest.raises(ValueError, match="reserved"):
        log_event("x", run_id="r", path=tmp_path / "p.jsonl", ts="nope")


@pytest.mark.parametrize("field", ["run_id", "event"])
def test_run_id_and_event_cannot_be_passed_twice(tmp_path, field):
    # Python itself rejects a duplicate keyword for these named parameters.
    with pytest.raises(TypeError):
        log_event("x", run_id="r", path=tmp_path / "p.jsonl", **{field: "nope"})


def test_non_json_values_are_written_as_strings(tmp_path):
    p = tmp_path / "p.jsonl"
    log_event("x", run_id="r", path=p, where=Path("/a/b"), day=date(2026, 11, 2), note="ünïcode")
    row = json.loads(p.read_text())
    assert row["where"] == "/a/b" and row["day"] == "2026-11-02" and row["note"] == "ünïcode"
