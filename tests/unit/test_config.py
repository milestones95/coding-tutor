"""Builder unit tests for tutor.config internals (T-003)."""

from pathlib import Path

import pytest

from tutor.config import REPO_ROOT, ConfigError, _apply_env, load_settings


def _load(tmp_path, **kw):
    kw.setdefault("env", {})
    kw.setdefault("dotenv_path", tmp_path / "none.env")
    return load_settings(**kw)


def test_apply_env_lowercases_and_nests():
    raw = {"sql": {"max_rows": 200}}
    _apply_env(raw, {"TUTOR__SQL__MAX_ROWS": "9", "TUTOR__LLM__FIELDS__FAILURE": "x:y", "OTHER": "1"})
    assert raw == {"sql": {"max_rows": "9"}, "llm": {"fields": {"failure": "x:y"}}}


@pytest.mark.parametrize("name", ["TUTOR__SQL", "TUTOR__SQL__", "TUTOR____MAX"])
def test_apply_env_rejects_malformed_names(name):
    with pytest.raises(ConfigError):
        _apply_env({}, {name: "1"})


def test_apply_env_cannot_descend_into_a_scalar():
    with pytest.raises(ConfigError, match="not a section"):
        _apply_env({"sql": {"max_rows": 1}}, {"TUTOR__SQL__MAX_ROWS__X": "1"})


def test_bad_value_error_names_key_but_not_value(tmp_path):
    with pytest.raises(ConfigError) as err:
        _load(tmp_path, env={"TUTOR__SQL__MAX_ROWS": "secret-looking-value-123"})
    assert "sql.max_rows" in str(err.value)
    assert "secret-looking-value-123" not in str(err.value)


def test_missing_required_key_is_an_error(tmp_path):
    toml = tmp_path / "t.toml"
    toml.write_text((REPO_ROOT / "tutor.toml").read_text().replace("max_steps = 10", ""))
    with pytest.raises(ConfigError, match="agent.max_steps"):
        _load(tmp_path, toml_path=toml)


def test_missing_file_and_bad_toml_raise_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        _load(tmp_path, toml_path=tmp_path / "nope.toml")
    bad = tmp_path / "bad.toml"
    bad.write_text("[sql\n")
    with pytest.raises(ConfigError, match="not valid TOML"):
        _load(tmp_path, toml_path=bad)


def test_relative_paths_resolve_against_repo_root_absolute_kept(tmp_path):
    s = _load(tmp_path, env={"TUTOR__PATHS__LOGS": "/abs/logs"})
    assert s.paths.capture_db == REPO_ROOT / "data" / "capture.db"
    assert s.paths.logs == Path("/abs/logs")
