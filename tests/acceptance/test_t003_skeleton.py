"""Acceptance tests for T-003: Python project skeleton, config, JSON-lines logging, test harness.

Tester-owned (`/test write T-003`, 2026-11-02). One or more tests per Done-when condition.
Interfaces, agreed with the human because the architecture doc doesn't name them:

    tutor.config.load_settings(toml_path=None, env=None, dotenv_path=None) -> Settings
    tutor.config.ConfigError            # message names the offending key
    tutor.logs.new_run_id() -> str
    tutor.logs.log_event(event, *, run_id, path=None, **fields) -> None

Done-when 3 (the test harness) is `tests/conftest.py`, tester-owned under rule 11, and is
checked by `tests/contract/test_network_block.py`.
"""

import json
import subprocess
import sys
import tomllib
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# architecture §11, with the defaults stated there
DEFAULTS = {
    ("paths", "capture_db"): "data/capture.db",
    ("paths", "eval_capture_db"): "data/reference/capture.db",
    ("paths", "analysis_db"): "data/analysis.db",
    ("paths", "fixture_db"): "evals/fixtures/progress.db",
    ("paths", "verdicts"): "data/labels/verdicts.csv",
    ("paths", "logs"): "logs",
    ("time", "timezone"): "America/New_York",
    ("condenser", "interval_s"): 120,
    ("condenser", "error_max_chars"): 500,
    ("condenser", "token_budget"): 16000,
    ("condenser", "rewrite_threshold"): 0.5,
    ("llm", "default"): "openai:gpt-5.5",
    ("llm", "generator"): "anthropic:claude-opus-5-5",
    ("llm", "max_output_retries"): 1,
    ("llm", "max_transient_retries"): 3,
    ("llm", "timeout_s"): 60,
    ("agent", "max_steps"): 10,
    ("sql", "timeout_s"): 5,
    ("sql", "max_rows"): 200,
}


def _load(tmp_path, **kw):
    from tutor.config import load_settings

    kw.setdefault("env", {})
    kw.setdefault("dotenv_path", tmp_path / "none.env")  # never pull the real .env into tests
    return load_settings(**kw)


def _same_path(value, rel: str) -> bool:
    p = Path(value)
    return (p if p.is_absolute() else REPO / p).resolve() == (REPO / rel).resolve()


# ---------------------------------------------------------------- Done-when 1


def test_dw1_pyproject_declares_python_313_and_dependencies():
    pp = tomllib.loads((REPO / "pyproject.toml").read_text())
    project = pp["project"]
    assert "3.13" in project.get("requires-python", ""), project.get("requires-python")
    deps = " ".join(project.get("dependencies", [])).lower()
    assert "pydantic" in deps and "python-dotenv" in deps, deps
    assert ">=2" in deps.split("pydantic", 1)[1].split()[0] or "pydantic>=2" in deps.replace(" ", ""), \
        "pydantic must be pinned to v2"
    dev = " ".join(
        pp.get("dependency-groups", {}).get("dev", [])
        + pp.get("tool", {}).get("uv", {}).get("dev-dependencies", [])
        + sum(project.get("optional-dependencies", {}).values(), [])
    ).lower()
    assert "pytest" in dev, "pytest must be a dev dependency"
    scripts = project.get("scripts", {})
    assert {"tutor", "tutor-eval"} <= scripts.keys(), scripts


@pytest.mark.parametrize("script", ["tutor", "tutor-eval"])
def test_dw1_console_scripts_print_help(script):
    exe = Path(sys.executable).parent / script
    assert exe.exists(), f"console script `{script}` is not installed in this environment (run `uv sync`)"
    out = subprocess.run([str(exe), "--help"], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert "usage" in (out.stdout + out.stderr).lower()


# ---------------------------------------------------------------- Done-when 2


def test_dw2_tutor_toml_holds_every_key_with_its_default():
    raw = tomllib.loads((REPO / "tutor.toml").read_text())
    for (section, key), default in DEFAULTS.items():
        assert section in raw and key in raw[section], f"tutor.toml lacks {section}.{key}"
        assert raw[section][key] == default, f"{section}.{key} = {raw[section][key]!r}, expected {default!r}"
    # unset by default: submit capture is not yet reliable; no judge override
    assert "submits_reliable_since" not in raw.get("capture", {}), "capture.submits_reliable_since must be unset until the human sets it"
    assert "judge" not in raw.get("llm", {})


def test_dw2_loaded_settings_match_the_defaults(tmp_path):
    s = _load(tmp_path)
    for (section, key), default in DEFAULTS.items():
        value = getattr(getattr(s, section), key)
        if section == "paths":
            assert _same_path(value, default), f"{section}.{key} = {value!r}"
        else:
            assert value == default, f"{section}.{key} = {value!r}, expected {default!r}"
    assert s.capture.submits_reliable_since is None
    assert s.llm.judge is None
    assert s.llm.fields == {}
    assert isinstance(s.prompts, dict)


def test_dw2_settings_are_frozen(tmp_path):
    s = _load(tmp_path)
    with pytest.raises(Exception):
        s.sql.max_rows = 1
    with pytest.raises(Exception):
        s.sql = None


def test_dw2_env_overrides_any_key_with_types(tmp_path):
    s = _load(tmp_path, env={
        "TUTOR__SQL__MAX_ROWS": "50",
        "TUTOR__CONDENSER__REWRITE_THRESHOLD": "0.6",
        "TUTOR__PATHS__CAPTURE_DB": "/tmp/elsewhere.db",
        "TUTOR__LLM__JUDGE": "anthropic:claude-opus-5-5",
        "TUTOR__LLM__FIELDS__FAILURE": "openai:other-model",
        "TUTOR__CAPTURE__SUBMITS_RELIABLE_SINCE": "2026-11-03",
    })
    assert s.sql.max_rows == 50
    assert s.condenser.rewrite_threshold == 0.6
    assert Path(s.paths.capture_db) == Path("/tmp/elsewhere.db")
    assert s.llm.judge == "anthropic:claude-opus-5-5"
    assert s.llm.fields == {"failure": "openai:other-model"}
    assert s.capture.submits_reliable_since == date(2026, 11, 3)
    assert s.sql.timeout_s == 5, "keys without an override keep the tutor.toml value"


def test_dw2_env_defaults_to_the_process_environment(tmp_path, monkeypatch):
    from tutor.config import load_settings

    monkeypatch.setenv("TUTOR__AGENT__MAX_STEPS", "7")
    s = load_settings(dotenv_path=tmp_path / "none.env")
    assert s.agent.max_steps == 7


def test_dw2_unknown_key_in_toml_raises_naming_it(tmp_path):
    from tutor.config import ConfigError

    toml = tmp_path / "tutor.toml"
    toml.write_text((REPO / "tutor.toml").read_text() + "\n[condensr]\ninterval_s = 60\n")
    with pytest.raises(ConfigError, match="condensr"):
        _load(tmp_path, toml_path=toml)


def test_dw2_unknown_key_in_env_raises_naming_it(tmp_path):
    from tutor.config import ConfigError

    with pytest.raises(ConfigError, match="(?i)max_rowz"):
        _load(tmp_path, env={"TUTOR__SQL__MAX_ROWZ": "1"})


def test_dw2_unrelated_env_vars_are_ignored(tmp_path):
    s = _load(tmp_path, env={"LCA_PROVIDER": "openai", "PATH": "/bin", "TUTORX": "1"})
    assert s.sql.max_rows == 200


# ---------------------------------------------------------------- Done-when 4


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_dw4_log_event_appends_one_json_object_per_line(tmp_path):
    from tutor.logs import log_event, new_run_id

    rid = new_run_id()
    path = tmp_path / "nested" / "pipeline.jsonl"
    log_event("loaded", run_id=rid, path=path, session_id="s-1", snapshots=3)
    log_event("excluded", run_id=rid, path=path, session_id="s-2", reason="non-attempt")
    rows = _lines(path)
    assert [r["event"] for r in rows] == ["loaded", "excluded"]
    assert all(r["run_id"] == rid for r in rows)
    assert rows[0]["session_id"] == "s-1" and rows[0]["snapshots"] == 3
    assert rows[1]["reason"] == "non-attempt"
    for r in rows:
        ts = datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
        assert ts.utcoffset() == timedelta(0), f"ts must be UTC: {r['ts']}"


def test_dw4_default_path_is_pipeline_jsonl_under_paths_logs(tmp_path, monkeypatch):
    from tutor.logs import log_event

    monkeypatch.setenv("TUTOR__PATHS__LOGS", str(tmp_path / "logs"))
    log_event("probe", run_id="r-1")
    rows = _lines(tmp_path / "logs" / "pipeline.jsonl")
    assert rows[-1]["event"] == "probe" and rows[-1]["run_id"] == "r-1"


def test_dw4_run_ids_are_unique_strings():
    from tutor.logs import new_run_id

    ids = {new_run_id() for _ in range(200)}
    assert len(ids) == 200 and all(isinstance(i, str) and i for i in ids)
