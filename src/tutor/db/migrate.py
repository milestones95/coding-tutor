"""Apply numbered migrations to analysis.db (architecture §3.3, D-032).

- Files are `NNNN_<name>.sql`, applied in order. Each one runs in its own transaction together
  with its `schema_migrations` row, so a migration either fully applies and is recorded, or
  leaves no trace.
- Why not `executescript(sql)` on its own: Python's sqlite3 commits before running a script, and
  a script that fails halfway keeps the statements that already ran. Here the connection is in
  autocommit mode and the script starts with its own `BEGIN`, so nothing is committed until the
  `COMMIT` sent after the version row is inserted, and a failure is rolled back.
- A migration never touches a capture DB: the target is resolved (symlinks, `..`) and compared
  with both capture paths before `sqlite3.connect`, which would otherwise create the file.
"""

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from tutor.config import Settings

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
FILE_NAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
# A migration's own transaction statements would break the one-transaction rule.
TRANSACTION_STATEMENT = re.compile(r"(?im)^\s*(begin|commit|rollback|end)\b(\s+transaction)?\s*;")


class MigrationError(Exception):
    """A refused target, a malformed migration set, or a migration that failed and was rolled back."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path


def discover(migrations_dir: Path) -> list[Migration]:
    """Every `.sql` file in `migrations_dir`, ordered by version. Bad names and gaps are errors."""
    found = []
    for path in sorted(migrations_dir.glob("*.sql")):
        m = FILE_NAME.match(path.name)
        if not m:
            raise MigrationError(f"{path.name}: migration files are named NNNN_<name>.sql")
        found.append(Migration(int(m.group(1)), m.group(2), path))
    versions = [m.version for m in found]
    if versions != list(range(1, len(found) + 1)):
        raise MigrationError(f"migration numbers must run 1..n with no gap or duplicate: {versions}")
    return found


def _refuse_capture(target: Path, settings: Settings) -> None:
    resolved = target.resolve()
    for key, capture in (("paths.capture_db", settings.paths.capture_db),
                         ("paths.eval_capture_db", settings.paths.eval_capture_db)):
        if resolved == Path(capture).resolve():
            raise MigrationError(f"refusing to migrate {target}: it is the capture DB ({key}); "
                                 "migrations only ever touch analysis.db")


def current_version(con: sqlite3.Connection) -> int:
    has_table = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'").fetchone()
    if not has_table:
        return 0
    return con.execute("SELECT coalesce(max(version), 0) FROM schema_migrations").fetchone()[0]


def _apply(con: sqlite3.Connection, m: Migration) -> None:
    sql = m.path.read_text()
    if TRANSACTION_STATEMENT.search(sql):
        raise MigrationError(f"{m.path.name}: contains its own BEGIN/COMMIT/ROLLBACK; migrate wraps each file in one")
    try:
        con.executescript("BEGIN;\n" + sql)
        con.execute("INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (m.version, m.name, datetime.now(UTC).isoformat(timespec="seconds")))
        con.execute("COMMIT")
    except sqlite3.Error as e:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise MigrationError(f"{m.path.name} failed and was rolled back: {e}") from None


def migrate(db_path: Path | str, *, settings: Settings, migrations_dir: Path | None = None) -> list[int]:
    """Apply pending migrations to `db_path`. Returns the versions applied by this run."""
    target = Path(db_path)
    _refuse_capture(target, settings)
    pending_all = discover(migrations_dir or MIGRATIONS_DIR)
    target.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(target, isolation_level=None)  # autocommit: transactions are explicit
    try:
        have = current_version(con)
        applied = []
        for m in pending_all:
            if m.version <= have:
                continue
            _apply(con, m)
            applied.append(m.version)
        return applied
    finally:
        con.close()
