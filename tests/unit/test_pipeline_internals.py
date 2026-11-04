"""Builder unit tests for tutor.analyzer.pipeline internals (T-011)."""

import sqlite3
from datetime import UTC, date, datetime

import pytest

from tutor.analyzer.pipeline import PipelineError, UPSERT_PROBLEM, _write, check, open_analysis_db, since_utc
from tutor.config import load_settings
from tutor.db.migrate import migrate


@pytest.fixture
def settings(tmp_path):
    return load_settings(env={"TUTOR__PATHS__ANALYSIS_DB": str(tmp_path / "a.db"),
                              "TUTOR__PATHS__CAPTURE_DB": str(tmp_path / "c.db"),
                              "TUTOR__PATHS__EVAL_CAPTURE_DB": str(tmp_path / "f.db"),
                              "TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


@pytest.mark.parametrize("day,utc", [
    (date(2026, 10, 31), datetime(2026, 10, 31, 4, tzinfo=UTC)),   # EDT: midnight = 04:00Z
    (date(2026, 11, 2), datetime(2026, 11, 2, 5, tzinfo=UTC)),     # EST after the change: 05:00Z
])
def test_since_is_local_midnight(settings, day, utc):
    assert since_utc(day, settings) == utc


def test_upsert_updates_instead_of_duplicating(settings):
    migrate(settings.paths.analysis_db, settings=settings)
    con = open_analysis_db(settings)
    _write(con, [(UPSERT_PROBLEM, [("p", "Old", "Easy", "[]")])])
    _write(con, [(UPSERT_PROBLEM, [("p", "New", "Hard", '["x"]')])])
    assert con.execute("SELECT * FROM problems").fetchall() == [("p", "New", "Hard", '["x"]')]


def test_a_failed_write_rolls_back(settings):
    migrate(settings.paths.analysis_db, settings=settings)
    con = open_analysis_db(settings)
    with pytest.raises(sqlite3.IntegrityError):
        _write(con, [(UPSERT_PROBLEM, [("p", "P", "Easy", "[]"), ("q", "Q", "Expert", "[]")])])
    assert con.execute("SELECT count(*) FROM problems").fetchone() == (0,)


def test_check_counts_a_missing_timeline_as_stale(settings):
    migrate(settings.paths.analysis_db, settings=settings)
    con = sqlite3.connect(settings.paths.analysis_db)
    con.execute("INSERT INTO session_analysis (session_id, condenser_version, updated_at) VALUES ('x', 'c1', 't')")
    con.commit()
    assert check(settings) == [("x", "c1", None)]


def test_an_older_migration_version_is_refused(settings, tmp_path):
    con = sqlite3.connect(settings.paths.analysis_db)
    con.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)")
    con.commit()
    with pytest.raises(PipelineError, match="tutor migrate"):
        open_analysis_db(settings)


def test_a_capture_path_is_refused(settings, tmp_path):
    s = load_settings(env={"TUTOR__PATHS__ANALYSIS_DB": str(tmp_path / "c.db"),
                           "TUTOR__PATHS__CAPTURE_DB": str(tmp_path / "c.db")}, dotenv_path=tmp_path / "none.env")
    with pytest.raises(PipelineError):
        open_analysis_db(s)
