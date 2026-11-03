"""Contract: secrets come only from env / `.env`, never from config (architecture §11).

Tester-owned (`/test write T-003`). `tutor.toml` is committed, so a key there would be
committed too. `Settings` holds no secrets, so it can be logged or printed safely.
"""

import os
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SENTINEL = "sk-SENTINEL-must-never-appear-0f3a9c"
SECRET_ENV = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")


def _toml(tmp_path: Path, extra: str) -> Path:
    p = tmp_path / "tutor.toml"
    p.write_text((REPO / "tutor.toml").read_text() + "\n" + extra + "\n")
    return p


def test_secret_in_tutor_toml_is_rejected(tmp_path):
    from tutor.config import ConfigError, load_settings

    toml = _toml(tmp_path, f'[secrets]\nopenai_api_key = "{SENTINEL}"')
    with pytest.raises(ConfigError) as err:
        load_settings(toml_path=toml, env={}, dotenv_path=tmp_path / "none.env")
    assert "secrets" in str(err.value) or "openai_api_key" in str(err.value)
    assert SENTINEL not in str(err.value), "the error message must not echo the secret"


def test_secret_via_tutor_env_override_is_rejected(tmp_path):
    from tutor.config import ConfigError, load_settings

    with pytest.raises(ConfigError) as err:
        load_settings(env={"TUTOR__LLM__API_KEY": SENTINEL}, dotenv_path=tmp_path / "none.env")
    assert "api_key" in str(err.value).lower()
    assert SENTINEL not in str(err.value)


def test_settings_schema_has_no_secret_fields(tmp_path):
    from tutor.config import load_settings

    s = load_settings(env={}, dotenv_path=tmp_path / "none.env")
    names = []

    def walk(obj, prefix=""):
        fields = getattr(type(obj), "model_fields", None)
        if fields is None:
            return
        for name in fields:
            names.append(prefix + name)
            walk(getattr(obj, name), prefix + name + ".")

    walk(s)
    # Match the last name segment only, so e.g. `condenser.token_budget` is fine.
    secret_name = re.compile(r"(^|_)(api_key|key|token|secret|password)$")
    bad = [n for n in names if secret_name.search(n.rsplit(".", 1)[-1].lower())]
    assert not bad, f"Settings must hold no secrets: {bad}"


def test_settings_never_carry_secret_values(tmp_path):
    from tutor.config import load_settings

    env = {name: SENTINEL for name in SECRET_ENV}
    s = load_settings(env=env, dotenv_path=tmp_path / "none.env")
    dumped = repr(s) + str(s)
    if hasattr(s, "model_dump_json"):
        dumped += s.model_dump_json()
    assert SENTINEL not in dumped


def test_dotenv_is_loaded_but_never_overrides_the_shell(tmp_path, monkeypatch):
    from tutor.config import load_settings

    dotenv = tmp_path / ".env"
    dotenv.write_text(f"OPENAI_API_KEY=from-dotenv-{SENTINEL}\nANTHROPIC_API_KEY=from-dotenv\n")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-shell")
    try:
        load_settings(dotenv_path=dotenv)
        assert os.environ.get("OPENAI_API_KEY") == f"from-dotenv-{SENTINEL}"
        assert os.environ.get("ANTHROPIC_API_KEY") == "from-shell"
    finally:
        os.environ.pop("OPENAI_API_KEY", None)
