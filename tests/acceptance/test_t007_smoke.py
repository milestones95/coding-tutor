"""Acceptance tests for T-007: the M0 checkpoint — load one session, make one logged call.

Tester-owned (`/test write T-007`, 2026-11-03). Interfaces (D-029, human approved):

    tutor smoke --session <id> [--model provider:model]
        loads <id> from `paths.eval_capture_db` (the frozen copy, opened immutable), fills
        `prompts/smoke/v1.md` with the problem title, makes one `structured()` call
        (field "smoke", output `{problem_slug: str}`) and prints one JSON line to stdout:
            {"session_id", "output": {"problem_slug"}, "call_id", "model": "provider:model", "cost_usd"}
        Exit 0. Any error: message on stderr, non-zero exit, and no request when the error is
        a config or lookup error.

Default tests run `tutor.cli.main([...])` in-process against a tiny capture DB and the fake
OpenAI server (`tests/_fake_openai.py`). The one `llm` test makes the real call:
    uv run pytest -m llm tests/acceptance/test_t007_smoke.py      # ≈ $0.001
"""

import hashlib
import json
from pathlib import Path

import pytest

from _capture_fixture import PROBLEM, build
from _fake_openai import start_fake_openai

REPO = Path(__file__).resolve().parents[2]
KEY = "sk-SENTINEL-t007-smoke-3b9d"
SLUG_OUT = {"problem_slug": "probe-problem"}
SESSION = "smoke-session-1"
IDLE = "smoke-session-idle"  # one snapshot, no judge events: excluded as no_activity

REAL_SESSION = "ebd80323-3d5b-4504-b5cd-1cff39c7ae82"  # one of the 8 frozen sessions (test_t004)


def _snaps(sid, n):
    return [{"session_id": sid, "ts": f"2026-11-01T10:0{i}:00.000Z", "code": f"# v{i}"} for i in range(n)]


@pytest.fixture
def capture(tmp_path):
    return build(tmp_path / "frozen.db",
                 sessions=[{"id": SESSION, "started_at": "2026-11-01T10:00:00.000Z"},
                           {"id": IDLE, "started_at": "2026-11-01T11:00:00.000Z"}],
                 snapshots=_snaps(SESSION, 3) + _snaps(IDLE, 1))


@pytest.fixture
def env(tmp_path, monkeypatch, capture):
    monkeypatch.setenv("TUTOR__PATHS__EVAL_CAPTURE_DB", str(capture))
    monkeypatch.setenv("TUTOR__PATHS__CAPTURE_DB", str(tmp_path / "live-does-not-exist.db"))
    monkeypatch.setenv("TUTOR__PATHS__VERDICTS", str(tmp_path / "no-verdicts.csv"))
    monkeypatch.setenv("TUTOR__PATHS__LOGS", str(tmp_path / "logs"))
    return tmp_path


@pytest.fixture
def server(monkeypatch, env):
    s = start_fake_openai(monkeypatch, key=KEY, output=SLUG_OUT)
    yield s
    s.close()


def smoke(*args):
    from tutor.cli import main

    return main(["smoke", *args])


def printed(capsys):
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "smoke prints one JSON line to stdout"
    return json.loads(out[-1])


def log_lines(tmp_path):
    path = tmp_path / "logs" / "llm_calls.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


# ---------------------------------------------------------------- Done-when 1: load one session, one logged call


def test_smoke_loads_the_session_and_makes_one_call(env, server, capsys):
    assert smoke("--session", SESSION) == 0
    assert len(server.requests) == 1
    assert PROBLEM["title"] in json.dumps(server.requests[0]["body"]), "the prompt is filled with the problem title"
    out = printed(capsys)
    assert out["session_id"] == SESSION
    assert out["output"] == SLUG_OUT
    assert out["model"] == "openai:gpt-5.5"
    assert out["cost_usd"] > 0


def test_smoke_writes_one_complete_log_line_with_a_cost(env, server, capsys):
    assert smoke("--session", SESSION) == 0
    [line] = log_lines(env)
    assert (line["field"], line["prompt_name"], line["prompt_version"]) == ("smoke", "smoke", "v1")
    assert (line["outcome"], line["error"]) == ("ok", None)
    assert line["cost_usd"] > 0
    assert line["call_id"] == printed(capsys)["call_id"]
    assert line["run_id"], "every line carries a run id"


def test_smoke_reads_the_frozen_copy_and_leaves_it_unchanged(env, server, capture):
    # paths.capture_db points at a file that doesn't exist: smoke must not need it.
    before = hashlib.sha256(capture.read_bytes()).hexdigest()
    assert smoke("--session", SESSION) == 0
    assert hashlib.sha256(capture.read_bytes()).hexdigest() == before
    assert not (env / "live-does-not-exist.db").exists()


def test_the_smoke_prompt_is_a_versioned_file_in_the_manifest():
    manifest = json.loads((REPO / "prompts" / "manifest.json").read_text())
    path = REPO / "prompts" / "smoke" / "v1.md"
    assert path.is_file()
    assert manifest.get("smoke/v1.md") == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("sid", ["no-such-session", IDLE])
def test_an_unknown_or_excluded_session_fails_before_any_call(env, server, capsys, sid):
    assert smoke("--session", sid) != 0
    assert server.requests == []
    assert sid in capsys.readouterr().err


# ---------------------------------------------------------------- Done-when 2: --model


def test_model_flag_overrides_the_configured_model(env, server, capsys, monkeypatch):
    # The configured default has no price, so without the flag smoke can't run at all.
    monkeypatch.setenv("TUTOR__LLM__DEFAULT", "openai:gpt-unpriced")
    assert smoke("--session", SESSION) != 0
    assert server.requests == []
    capsys.readouterr()

    assert smoke("--session", SESSION, "--model", "openai:gpt-5.5") == 0
    [req] = server.requests
    assert req["body"]["model"] == "gpt-5.5"
    assert printed(capsys)["model"] == "openai:gpt-5.5"
    assert log_lines(env)[-1]["model"] == "gpt-5.5"


@pytest.mark.parametrize("ref", ["gpt-5.5", "gemini:gemini-x"])
def test_a_bad_model_flag_fails_with_the_config_error_before_any_call(env, server, capsys, ref):
    assert smoke("--session", SESSION, "--model", ref) != 0
    assert server.requests == []
    err = capsys.readouterr().err
    assert ref.split(":")[0] in err, "the LLMConfigError message is shown"


# ---------------------------------------------------------------- the real call (deselected by default)


@pytest.mark.llm
def test_smoke_makes_a_real_logged_call(tmp_path, monkeypatch, capsys):
    frozen = REPO / "data" / "reference" / "capture.db"
    if not frozen.exists():
        pytest.skip("needs the frozen copy at data/reference/capture.db")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setenv("TUTOR__PATHS__LOGS", str(tmp_path / "logs"))
    assert smoke("--session", REAL_SESSION) == 0
    out = printed(capsys)
    assert isinstance(out["output"]["problem_slug"], str) and out["output"]["problem_slug"]
    [line] = log_lines(tmp_path)
    assert line["outcome"] == "ok" and line["cost_usd"] > 0
    assert line["input_tokens"] > 0 and line["output_tokens"] > 0
