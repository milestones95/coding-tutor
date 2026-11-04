"""Builder unit tests for tutor.db.migrate internals (T-008)."""

import sqlite3

import pytest

from tutor.db.migrate import MIGRATIONS_DIR, MigrationError, current_version, discover, migrate
from tutor.config import load_settings


def _settings(tmp_path):
    return load_settings(env={"TUTOR__PATHS__CAPTURE_DB": str(tmp_path / "c.db"),
                              "TUTOR__PATHS__EVAL_CAPTURE_DB": str(tmp_path / "f.db")},
                         dotenv_path=tmp_path / "none.env")


def test_discover_parses_version_and_name_in_order(tmp_path):
    for name in ("0002_add_x.sql", "0001_init.sql"):
        (tmp_path / name).write_text("SELECT 1;")
    assert [(m.version, m.name) for m in discover(tmp_path)] == [(1, "init"), (2, "add_x")]


@pytest.mark.parametrize("names", [["1_init.sql"], ["0001_Init.sql"], ["0001_a.sql", "0003_c.sql"],
                                   ["0002_a.sql"]])
def test_discover_rejects_bad_names_and_gaps(tmp_path, names):
    for name in names:
        (tmp_path / name).write_text("SELECT 1;")
    with pytest.raises(MigrationError):
        discover(tmp_path)


def test_the_real_migrations_are_discoverable():
    assert [m.name for m in discover(MIGRATIONS_DIR)][0] == "init"


def test_current_version_is_zero_on_an_empty_db():
    assert current_version(sqlite3.connect(":memory:")) == 0


@pytest.mark.parametrize("stmt", ["BEGIN;", "COMMIT;", "rollback;", "BEGIN TRANSACTION;"])
def test_a_migration_with_its_own_transaction_is_refused(tmp_path, stmt):
    mig = tmp_path / "m"
    mig.mkdir()
    (mig / "0001_x.sql").write_text(f"CREATE TABLE schema_migrations (version INTEGER, name TEXT, applied_at TEXT);\n{stmt}\n")
    with pytest.raises(MigrationError, match="0001_x.sql"):
        migrate(tmp_path / "t.db", settings=_settings(tmp_path), migrations_dir=mig)


def test_the_error_names_the_failing_file(tmp_path):
    mig = tmp_path / "m"
    mig.mkdir()
    (mig / "0001_bad.sql").write_text("NOT SQL;\n")
    with pytest.raises(MigrationError, match="0001_bad.sql.*rolled back"):
        migrate(tmp_path / "t.db", settings=_settings(tmp_path), migrations_dir=mig)
