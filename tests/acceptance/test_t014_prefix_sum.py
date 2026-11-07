"""Acceptance tests for T-014: migration 0002 adds `prefix_sum` to the algorithm labels (D-044).

Tester-owned (`/test write T-014`, 2026-11-07). Uses the D-032 interface
(`tutor.db.migrate.migrate(db_path, *, settings, migrations_dir=None)`). A "version-1 database"
is built by applying only 0001 from a temporary migrations folder, then filled with rows, and
then upgraded with the real migrations folder.
"""

import re
import sqlite3
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO / "src" / "tutor" / "db" / "migrations"
OLD_LABELS = ["hash_map", "two_pointers", "sliding_window", "binary_search", "stack", "heap", "bfs",
              "dfs_backtracking", "dynamic_programming", "greedy", "intervals", "linked_list", "tree_traversal",
              "trie", "union_find", "graph_topological_sort", "bit_manipulation", "math"]


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__CAPTURE_DB": str(tmp_path / "capture.db"),
                              "TUTOR__PATHS__EVAL_CAPTURE_DB": str(tmp_path / "frozen.db"),
                              "TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def migrate(*a, **kw):
    from tutor.db.migrate import migrate as m

    return m(*a, **kw)


def _seed_parents(con, sid):
    con.execute("INSERT OR IGNORE INTO problems (slug, title, difficulty, tags) VALUES ('p', 'P', 'Easy', '[]')")
    con.execute(
        "INSERT INTO sessions (session_id, slug, attempted_at_utc, attempted_date_local, time_to_finish_min, status,"
        " status_source, run_count, submit_count, loaded_at) VALUES (?, 'p', '2026-11-01T10:00:00.000Z',"
        " '2026-11-01', 5.0, 'passed', 'capture_submit', 1, 1, 't')", (sid,))
    con.execute("INSERT INTO session_analysis (session_id, failure_type, condenser_version, updated_at)"
                " VALUES (?, 'none', 'c1', 't')", (sid,))


@pytest.fixture
def v1_with_rows(tmp_path, settings):
    """A database at version 1 holding algorithm rows, as one built before T-014 would be."""
    only_0001 = tmp_path / "only-0001"
    only_0001.mkdir()
    (only_0001 / "0001_init.sql").write_text((MIGRATIONS / "0001_init.sql").read_text())
    path = tmp_path / "analysis.db"
    assert migrate(path, settings=settings, migrations_dir=only_0001) == [1]
    con = sqlite3.connect(path)
    for sid, labels in {"s1": ["hash_map", "two_pointers"], "s2": ["dynamic_programming"]}.items():
        _seed_parents(con, sid)
        con.executemany("INSERT INTO session_algorithms VALUES (?, ?)", [(sid, lab) for lab in labels])
    con.commit()
    con.close()
    return path


# ---------------------------------------------------------------- Done-when 1: the migration file


def test_dw1_0002_exists_with_a_header_about_existing_rows():
    files = sorted(p.name for p in MIGRATIONS.glob("*.sql"))
    assert "0002_add_prefix_sum.sql" in files
    text = (MIGRATIONS / "0002_add_prefix_sum.sql").read_text()
    header = " ".join(line for line in text.splitlines() if line.startswith("--"))
    assert re.search(r"(?i)\brows?\b", header), "the header says what happens to existing rows (§3.3)"
    assert "prefix_sum" in text


# ---------------------------------------------------------------- Done-when 2: versions


def test_dw2_a_fresh_db_migrates_to_version_2(tmp_path, settings):
    path = tmp_path / "fresh.db"
    assert migrate(path, settings=settings) == [1, 2]
    assert migrate(path, settings=settings) == [], "a second run applies nothing"


def test_dw2_a_version_1_db_upgrades_to_2(v1_with_rows, settings):
    assert migrate(v1_with_rows, settings=settings) == [2]
    versions = [v for (v,) in sqlite3.connect(v1_with_rows).execute("SELECT version FROM schema_migrations ORDER BY 1")]
    assert versions == [1, 2]


# ---------------------------------------------------------------- Done-when 3: rows kept, labels checked


def test_dw3_existing_algorithm_rows_survive_the_upgrade(v1_with_rows, settings):
    migrate(v1_with_rows, settings=settings)
    rows = sorted(sqlite3.connect(v1_with_rows).execute("SELECT session_id, label FROM session_algorithms"))
    assert rows == [("s1", "hash_map"), ("s1", "two_pointers"), ("s2", "dynamic_programming")]


def test_dw3_prefix_sum_is_accepted_and_off_list_labels_are_not(v1_with_rows, settings):
    migrate(v1_with_rows, settings=settings)
    con = sqlite3.connect(v1_with_rows)
    _seed_parents(con, "s3")
    con.execute("INSERT INTO session_algorithms VALUES ('s3', 'prefix_sum')")
    for label in OLD_LABELS:
        con.execute("INSERT INTO session_algorithms VALUES ('s3', ?)", (label,))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO session_algorithms VALUES ('s3', 'hashmap')")


def test_dw3_the_primary_key_and_index_survive(v1_with_rows, settings):
    migrate(v1_with_rows, settings=settings)
    con = sqlite3.connect(v1_with_rows)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO session_algorithms VALUES ('s1', 'hash_map')")   # (session_id, label) is the key
    names = {n for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert "algorithms_label" in names


def test_dw3_algorithm_label_enum_has_the_19_labels():
    from tutor.models import AlgorithmLabel

    assert {a.value for a in AlgorithmLabel} == set(OLD_LABELS) | {"prefix_sum"}
