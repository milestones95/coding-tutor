"""Contract: analysis.db migrations — architecture §3.3. Tester-owned; kept for the life of the
project (`/test write T-008`, 2026-11-03; interfaces D-032).

- An applied migration is never edited: each file's sha256 matches
  `src/tutor/db/migrations/manifest.json`, and a schema change has to be a new file.
- Files are `NNNN_<name>.sql`, numbered 0001, 0002, … with no gap or duplicate.
- No `IF NOT EXISTS`: a migration that runs twice is a bug, and IF NOT EXISTS would hide it.
- Migrations never touch a capture DB: `migrate` refuses `paths.capture_db` and
  `paths.eval_capture_db`, however the path is spelled, without opening either file.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO / "src" / "tutor" / "db" / "migrations"
NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def _sql_files():
    return sorted(MIGRATIONS.glob("*.sql"))


def test_there_is_at_least_one_migration():
    assert _sql_files(), f"no migrations under {MIGRATIONS.relative_to(REPO)}"


def test_every_migration_matches_its_manifest_hash():
    manifest = json.loads((MIGRATIONS / "manifest.json").read_text())
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in _sql_files()}
    assert set(manifest) == set(files), (
        f"manifest and files differ: missing from manifest {sorted(set(files) - set(manifest))}, "
        f"stale entries {sorted(set(manifest) - set(files))}")
    changed = [n for n in files if manifest[n] != files[n]]
    assert not changed, f"applied migrations were edited (write a new migration instead): {changed}"


def test_migrations_are_numbered_without_gaps():
    names = [p.name for p in _sql_files()]
    bad = [n for n in names if not NAME.match(n)]
    assert not bad, f"not NNNN_<name>.sql: {bad}"
    numbers = [int(NAME.match(n).group(1)) for n in names]
    assert numbers == list(range(1, len(numbers) + 1)), f"numbers must run 1..n with no gap or duplicate: {numbers}"


def test_no_migration_uses_if_not_exists():
    hits = [p.name for p in _sql_files() if re.search(r"(?i)\bif\s+not\s+exists\b", p.read_text())]
    assert not hits, f"IF NOT EXISTS in {hits}: a migration that runs twice is a bug, not something to hide"


# ---------------------------------------------------------------- never a capture DB


def _settings(tmp_path, capture, frozen):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__CAPTURE_DB": str(capture), "TUTOR__PATHS__EVAL_CAPTURE_DB": str(frozen),
                              "TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


@pytest.fixture
def captures(tmp_path):
    capture, frozen = tmp_path / "capture.db", tmp_path / "reference" / "capture.db"
    frozen.parent.mkdir()
    capture.write_bytes(b"live capture bytes")
    frozen.write_bytes(b"frozen capture bytes")
    return capture, frozen


def _target(tmp_path, which, capture, frozen):
    real = capture if which.endswith("live") else frozen
    if which.startswith("symlink"):
        link = tmp_path / f"link-{which}.db"
        link.symlink_to(real)
        return link
    if which.startswith("dotted"):
        return real.parent / "." / ".." / real.parent.name / real.name
    return real


@pytest.mark.parametrize("which", ["plain-live", "plain-frozen", "dotted-live", "dotted-frozen",
                                   "symlink-live", "symlink-frozen"])
def test_migrate_refuses_a_capture_db(tmp_path, captures, which):
    from tutor.db.migrate import MigrationError, migrate

    capture, frozen = captures
    target = _target(tmp_path, which, capture, frozen)
    with pytest.raises(MigrationError):
        migrate(target, settings=_settings(tmp_path, capture, frozen))
    assert capture.read_bytes() == b"live capture bytes"
    assert frozen.read_bytes() == b"frozen capture bytes"


def test_migrate_refuses_a_capture_db_that_does_not_exist_yet(tmp_path):
    from tutor.db.migrate import MigrationError, migrate

    capture, frozen = tmp_path / "capture.db", tmp_path / "frozen.db"
    with pytest.raises(MigrationError):
        migrate(capture, settings=_settings(tmp_path, capture, frozen))
    assert not capture.exists(), "refusing must happen before the file is opened (and so created)"
