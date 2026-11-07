"""Acceptance tests for T-008: analysis.db migrations (architecture §3.2, §3.3).

Tester-owned (`/test write T-008`, 2026-11-03). Interfaces (D-032, human approved):

    tutor.db.migrate.migrate(db_path, *, settings, migrations_dir=None) -> list[int]
        applies pending migrations in order, each in one transaction, recording each in
        schema_migrations; returns the versions applied by this run.
    tutor.db.migrate.MigrationError   # refused target, or a migration that failed (rolled back)
    tutor migrate [--db PATH]         # default paths.analysis_db; exit 0, or 1 with stderr (D-030)

The capture-path refusal and the manifest are in tests/contract/test_migrations.py.
"""

import re
import sqlite3
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MIGRATION = REPO / "src" / "tutor" / "db" / "migrations" / "0001_init.sql"
TABLES = {"schema_migrations", "problems", "sessions", "condensed_timelines", "session_analysis",
          "session_algorithms", "field_provenance"}
INDEXES = {"sessions_date", "sessions_slug", "sessions_status", "analysis_failure", "algorithms_label"}


def _architecture_ddl() -> str:
    doc = (REPO / "docs" / "architecture.md").read_text()
    section = doc.split("### 3.2", 1)[1].split("### 3.3", 1)[0]
    return re.search(r"```sql\n(.*?)```", section, re.S).group(1)


def _normalise(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", "", sql)
    return re.sub(r"\s+", " ", sql).replace("( ", "(").replace(" )", ")").strip()


def _schema(con) -> dict[str, str]:
    rows = con.execute("SELECT name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'")
    return {name: _normalise(sql) for name, sql in rows}


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__ANALYSIS_DB": str(tmp_path / "analysis.db"),
                              "TUTOR__PATHS__CAPTURE_DB": str(tmp_path / "capture.db"),
                              "TUTOR__PATHS__EVAL_CAPTURE_DB": str(tmp_path / "frozen.db"),
                              "TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def migrate(*a, **kw):
    from tutor.db.migrate import migrate as m

    return m(*a, **kw)


@pytest.fixture
def db(tmp_path, settings):
    path = tmp_path / "analysis.db"
    migrate(path, settings=settings)
    con = sqlite3.connect(path)
    yield con
    con.close()


# ---------------------------------------------------------------- Done-when 1: the §3.2 DDL, exactly


def test_dw1_the_migration_is_the_architecture_ddl(tmp_path, settings):
    # Only 0001 applied: later migrations (0002, T-014) legitimately change the schema §3.2 shows.
    only_0001 = tmp_path / "only-0001"
    only_0001.mkdir()
    (only_0001 / MIGRATION.name).write_text(MIGRATION.read_text())
    path = tmp_path / "v1.db"
    migrate(path, settings=settings, migrations_dir=only_0001)
    ref = sqlite3.connect(":memory:")
    ref.executescript(_architecture_ddl())
    assert _schema(sqlite3.connect(path)) == _schema(ref), "0001_init.sql must create exactly the §3.2 schema"


def test_dw1_the_migration_starts_with_a_header_about_existing_rows():
    lines = MIGRATION.read_text().splitlines()
    header = []
    for line in lines:
        if not line.startswith("--"):
            break
        header.append(line)
    assert header, "0001_init.sql starts with a -- header comment (§3.3)"
    assert re.search(r"(?i)\brows?\b", " ".join(header)), "the header says what happens to existing rows"


# ---------------------------------------------------------------- Done-when 2: creates, records, idempotent


def test_dw2_migrate_creates_every_table_and_index(tmp_path, settings):
    path = tmp_path / "analysis.db"
    assert not path.exists()
    assert migrate(path, settings=settings) == [1, 2]   # 0002_add_prefix_sum since T-014
    con = sqlite3.connect(path)
    names = {n: t for t, n in con.execute("SELECT type, name FROM sqlite_master")}
    assert TABLES <= {n for n, t in names.items() if t == "table"}
    assert INDEXES <= {n for n, t in names.items() if t == "index"}
    rows = con.execute("SELECT version, name, applied_at FROM schema_migrations ORDER BY version").fetchall()
    assert [(v, n) for v, n, _ in rows] == [(1, "init"), (2, "add_prefix_sum")]
    for _, _, applied_at in rows:
        assert re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d", applied_at), "applied_at is ISO-8601"


def test_dw2_a_second_run_applies_nothing_and_changes_nothing(tmp_path, settings):
    path = tmp_path / "analysis.db"
    migrate(path, settings=settings)
    con = sqlite3.connect(path)
    before = (_schema(con), con.execute("SELECT * FROM schema_migrations").fetchall())
    con.close()
    assert migrate(path, settings=settings) == []
    con = sqlite3.connect(path)
    assert (_schema(con), con.execute("SELECT * FROM schema_migrations").fetchall()) == before


def test_dw2_cli_migrate_defaults_to_paths_analysis_db(tmp_path, settings, monkeypatch, capsys):
    from tutor.cli import main

    monkeypatch.setenv("TUTOR__PATHS__ANALYSIS_DB", str(tmp_path / "analysis.db"))
    monkeypatch.setenv("TUTOR__PATHS__CAPTURE_DB", str(tmp_path / "capture.db"))
    monkeypatch.setenv("TUTOR__PATHS__EVAL_CAPTURE_DB", str(tmp_path / "frozen.db"))
    assert main(["migrate"]) == 0
    assert (tmp_path / "analysis.db").exists()
    assert main(["migrate", "--db", str(tmp_path / "other.db")]) == 0
    assert (tmp_path / "other.db").exists()


def test_dw2_cli_migrate_refusal_exits_1_with_a_message(tmp_path, monkeypatch, capsys):
    from tutor.cli import main

    capture = tmp_path / "capture.db"
    monkeypatch.setenv("TUTOR__PATHS__CAPTURE_DB", str(capture))
    monkeypatch.setenv("TUTOR__PATHS__EVAL_CAPTURE_DB", str(tmp_path / "frozen.db"))
    assert main(["migrate", "--db", str(capture)]) == 1
    assert capsys.readouterr().err.strip()
    assert not capture.exists()


# ---------------------------------------------------------------- Done-when 3: one transaction per migration

# Test migrations follow the §3.2 convention: 0001 creates schema_migrations itself.
SCHEMA_MIGRATIONS = ("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL,"
                     " applied_at TEXT NOT NULL);\n")


def test_dw3_a_failing_migration_rolls_back_to_the_previous_version(tmp_path, settings):
    from tutor.db.migrate import MigrationError

    mig = tmp_path / "migs"
    mig.mkdir()
    (mig / "0001_first.sql").write_text("-- test migration; no existing rows\n" + SCHEMA_MIGRATIONS
                                         + "CREATE TABLE a (x INTEGER);\n")
    (mig / "0002_broken.sql").write_text(
        "-- test migration; no existing rows\n"
        "CREATE TABLE b (y INTEGER);\n"
        "INSERT INTO a VALUES (1);\n"
        "THIS IS NOT SQL;\n")
    path = tmp_path / "t.db"
    with pytest.raises(MigrationError):
        migrate(path, settings=settings, migrations_dir=mig)
    con = sqlite3.connect(path)
    tables = {n for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "a" in tables and "b" not in tables, "the failed migration left a partial table"
    assert con.execute("SELECT count(*) FROM a").fetchone() == (0,), "the failed migration's rows stayed"
    assert [v for (v,) in con.execute("SELECT version FROM schema_migrations")] == [1]


def test_dw3_after_fixing_the_migration_it_applies(tmp_path, settings):
    from tutor.db.migrate import MigrationError

    mig = tmp_path / "migs"
    mig.mkdir()
    (mig / "0001_first.sql").write_text(SCHEMA_MIGRATIONS + "CREATE TABLE a (x INTEGER);\n")
    (mig / "0002_next.sql").write_text("CREATE TABLE b (y INTEGER);\nNOT SQL;\n")
    path = tmp_path / "t.db"
    with pytest.raises(MigrationError):
        migrate(path, settings=settings, migrations_dir=mig)
    (mig / "0002_next.sql").write_text("CREATE TABLE b (y INTEGER);\n")
    assert migrate(path, settings=settings, migrations_dir=mig) == [2]


# ---------------------------------------------------------------- Done-when 6: CHECK constraints


def _seed(con):
    con.execute("INSERT INTO problems (slug, title, difficulty, tags) VALUES ('two-sum', 'Two Sum', 'Easy', '[]')")
    con.execute(
        "INSERT INTO sessions (session_id, slug, attempted_at_utc, attempted_date_local, time_to_finish_min, status,"
        " leetcode_verdict, tests_passed, tests_total, status_source, run_count, submit_count, loaded_at)"
        " VALUES ('s1', 'two-sum', '2026-11-01T10:00:00Z', '2026-11-01', 12.5, 'passed', 'Accepted', 5, 5,"
        " 'capture_submit', 2, 1, '2026-11-03T00:00:00Z')")
    con.execute("INSERT INTO session_analysis (session_id, failure_type, failure_type_source, condenser_version,"
                " updated_at) VALUES ('s1', 'none', 'rule', 'c1', '2026-11-03T00:00:00Z')")


def test_dw6_valid_rows_are_accepted(db):
    _seed(db)
    db.execute("INSERT INTO condensed_timelines VALUES ('s1', 'c1', '{}', 'text', 10, 0, '2026-11-03T00:00:00Z')")
    db.execute("INSERT INTO session_algorithms VALUES ('s1', 'hash_map')")
    for status in ("failed_wrong_answer", "failed_too_slow", "failed_output_limit", "failed_runtime_error",
                   "not_submitted", "unknown"):
        db.execute("UPDATE sessions SET status = ? WHERE session_id = 's1'", (status,))


@pytest.mark.parametrize("sql", [
    "UPDATE sessions SET status = 'failed' WHERE session_id = 's1'",
    "UPDATE sessions SET status_source = 'llm' WHERE session_id = 's1'",
    "UPDATE session_analysis SET failure_type = 'typo' WHERE session_id = 's1'",
    "UPDATE session_analysis SET failure_type_source = 'human' WHERE session_id = 's1'",
    "INSERT INTO session_algorithms VALUES ('s1', 'hashmap')",
    "INSERT INTO condensed_timelines VALUES ('s1', 'c1', '{}', 'text', 10, 2, '2026-11-03T00:00:00Z')",
    "INSERT INTO problems (slug, title, difficulty, tags) VALUES ('x', 'X', 'Expert', '[]')",
    "INSERT INTO field_provenance VALUES ('s1', 'status', 'p', 'v1', 'openai', 'm', 'r', 'c', 't')",
])
def test_dw6_check_constraints_reject_bad_values(db, sql):
    _seed(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql)
