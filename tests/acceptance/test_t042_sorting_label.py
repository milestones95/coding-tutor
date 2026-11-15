"""Acceptance tests for T-042: `sorting` joins the algorithm labels, which become rows in an
`algorithm_labels` table (D-070, building D-050's deferred table). Tester-owned (`/test write T-042`,
2026-11-14). Interface (D-032): `tutor.db.migrate.migrate(db_path, *, settings, migrations_dir=None)`.

Done-when 4 (one label list everywhere) is the contract test `tests/contract/test_label_lists.py`.
Done-when 5 (the human's call on Merge Sorted Array) is checked at `/test run` from the task log.

Enforcement is tested on a plain `sqlite3.connect` with no PRAGMA: an off-list label must be refused
however the database is opened (SQLite only enforces REFERENCES when `foreign_keys` is on).
"""

import re
import sqlite3
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO / "src" / "tutor" / "db" / "migrations"
LABELS_19 = {"hash_map", "two_pointers", "sliding_window", "binary_search", "stack", "heap", "bfs",
             "dfs_backtracking", "dynamic_programming", "greedy", "intervals", "linked_list", "tree_traversal",
             "trie", "union_find", "graph_topological_sort", "bit_manipulation", "math", "prefix_sum"}
LABELS_20 = LABELS_19 | {"sorting"}


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__CAPTURE_DB": str(tmp_path / "capture.db"),
                              "TUTOR__PATHS__EVAL_CAPTURE_DB": str(tmp_path / "frozen.db"),
                              "TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


def migrate(*a, **kw):
    from tutor.db.migrate import migrate as m

    return m(*a, **kw)


def _new_migration() -> Path:
    found = sorted(MIGRATIONS.glob("0003_*.sql"))
    assert len(found) == 1, "exactly one migration numbered 0003"
    return found[0]


def _seed(con, sid):
    con.execute("INSERT OR IGNORE INTO problems (slug, title, difficulty, tags) VALUES ('p', 'P', 'Easy', '[]')")
    con.execute(
        "INSERT INTO sessions (session_id, slug, attempted_at_utc, attempted_date_local, time_to_finish_min, status,"
        " status_source, run_count, submit_count, loaded_at) VALUES (?, 'p', '2026-11-01T10:00:00.000Z',"
        " '2026-11-01', 5.0, 'passed', 'capture_submit', 1, 1, 't')", (sid,))
    con.execute("INSERT INTO session_analysis (session_id, failure_type, condenser_version, updated_at)"
                " VALUES (?, 'none', 'c1', 't')", (sid,))


@pytest.fixture
def v2_with_rows(tmp_path, settings):
    """A database at version 2 (0001 + 0002) holding algorithm rows, as one built before T-042 would be."""
    upto2 = tmp_path / "upto-0002"
    upto2.mkdir()
    for name in ("0001_init.sql", "0002_add_prefix_sum.sql"):
        (upto2 / name).write_text((MIGRATIONS / name).read_text())
    path = tmp_path / "analysis.db"
    assert migrate(path, settings=settings, migrations_dir=upto2) == [1, 2]
    con = sqlite3.connect(path)
    for sid, labels in {"s1": ["hash_map", "two_pointers"], "s2": ["prefix_sum"]}.items():
        _seed(con, sid)
        con.executemany("INSERT INTO session_algorithms VALUES (?, ?)", [(sid, lab) for lab in labels])
    con.commit()
    con.close()
    return path


# ---------------------------------------------------------------- Done-when 1: the migration


def test_dw1_0003_exists_and_its_header_says_what_happens_to_existing_rows():
    text = _new_migration().read_text()
    header = " ".join(line for line in text.splitlines() if line.startswith("--"))
    assert re.search(r"(?i)\brows?\b", header), "the header says what happens to existing rows (§3.3)"
    assert "algorithm_labels" in text and "sorting" in text


def test_dw1_a_fresh_db_migrates_to_version_3(tmp_path, settings):
    path = tmp_path / "fresh.db"
    assert migrate(path, settings=settings) == [1, 2, 3]
    assert migrate(path, settings=settings) == []


def test_dw1_a_version_2_db_upgrades_and_keeps_every_row(v2_with_rows, settings):
    assert migrate(v2_with_rows, settings=settings) == [3]
    rows = sorted(sqlite3.connect(v2_with_rows).execute("SELECT session_id, label FROM session_algorithms"))
    assert rows == [("s1", "hash_map"), ("s1", "two_pointers"), ("s2", "prefix_sum")]


def test_dw1_algorithm_labels_holds_exactly_the_20_labels(v2_with_rows, settings):
    migrate(v2_with_rows, settings=settings)
    got = {lab for (lab,) in sqlite3.connect(v2_with_rows).execute("SELECT label FROM algorithm_labels")}
    assert got == LABELS_20


def test_dw1_sorting_is_accepted_and_an_off_list_label_is_refused_on_a_plain_connection(v2_with_rows, settings):
    migrate(v2_with_rows, settings=settings)
    con = sqlite3.connect(v2_with_rows)   # no PRAGMA foreign_keys: enforcement can't depend on it
    _seed(con, "s3")
    con.execute("INSERT INTO session_algorithms VALUES ('s3', 'sorting')")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO session_algorithms VALUES ('s3', 'hashmap')")


def test_dw1_a_new_label_is_a_row_insert_not_a_schema_change(v2_with_rows, settings):
    """The point of the table (D-050): adding a label later needs no table rebuild."""
    migrate(v2_with_rows, settings=settings)
    con = sqlite3.connect(v2_with_rows)
    _seed(con, "s4")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO session_algorithms VALUES ('s4', 'new_label')")
    con.execute("INSERT INTO algorithm_labels (label) VALUES ('new_label')")
    con.execute("INSERT INTO session_algorithms VALUES ('s4', 'new_label')")


def test_dw1_the_primary_key_and_index_survive(v2_with_rows, settings):
    migrate(v2_with_rows, settings=settings)
    con = sqlite3.connect(v2_with_rows)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO session_algorithms VALUES ('s1', 'hash_map')")
    names = {n for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert "algorithms_label" in names


def test_dw1_architecture_describes_the_table():
    doc = (REPO / "docs" / "architecture.md").read_text()
    assert "algorithm_labels" in doc and "0003" in doc


# ---------------------------------------------------------------- Done-when 2: sorting everywhere


def test_dw2_the_enum_has_the_20_labels():
    from tutor.models import AlgorithmLabel

    assert {a.value for a in AlgorithmLabel} == LABELS_20


def test_dw2_architecture_and_skill_list_sorting():
    assert "sorting" in (REPO / "docs" / "architecture.md").read_text()
    assert "`sorting`" in (REPO / ".claude" / "skills" / "synthetic-spec" / "SKILL.md").read_text()


# ---------------------------------------------------------------- Done-when 3: algorithm prompt v2


def _body(version: str) -> list[str]:
    text = (REPO / "prompts" / "algorithm" / f"{version}.md").read_text()
    return [ln for ln in text.split("---", 2)[2].splitlines() if ln.strip()]


def test_dw3_v2_is_pinned_and_in_the_manifest_and_v1_is_unchanged():
    import json

    from tutor.config import load_settings
    from tutor.prompts import load_prompt

    assert load_settings().prompts.get("algorithm") == "v2"
    manifest = json.loads((REPO / "prompts" / "manifest.json").read_text())
    assert manifest.get("algorithm/v2.md") == load_prompt("algorithm", "v2").sha256
    assert manifest["algorithm/v1.md"] == load_prompt("algorithm", "v1").sha256


def test_dw3_v2_is_v1_plus_a_sorting_line_only():
    from tutor.prompts import load_prompt

    v1, v2 = load_prompt("algorithm", "v1"), load_prompt("algorithm", "v2")
    assert tuple(v2.variables) == tuple(v1.variables)
    removed = [ln for ln in _body("v1") if ln not in _body("v2")]
    added = [ln for ln in _body("v2") if ln not in _body("v1")]
    assert not removed, f"v2 changes or drops v1 lines: {removed}"
    assert 1 <= len(added) <= 2 and any(ln.lstrip().startswith("- sorting:") for ln in added), added


def test_dw3_v2_names_no_dataset_problem():
    import json

    text = (REPO / "prompts" / "algorithm" / "v2.md").read_text().lower()
    names = set()
    for line in (REPO / "evals/data/sessions/synthetic/specs.jsonl").read_text().splitlines():
        if line.strip():
            p = json.loads(line)["problem"]
            names |= {p["slug"].lower(), p["title"].lower()}
    assert not [n for n in names if n in text], "rule 9"
