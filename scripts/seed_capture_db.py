"""One-off: seed this repo's live capture DB from the old capture DB (T-002, D-015).

    python3 scripts/seed_capture_db.py --source ../leetcode-analyzer/data/leetcode.db

Why it is shaped this way:
- SQLite's backup API copies a consistent snapshot, including writes still sitting in the
  source's -wal file. A plain `cp` of the .db file would miss those.
- The source is opened read-only and hashed before and after. If the hash changes, the old
  file was touched and the script fails. The old file is kept untouched as the backup.
- It refuses to overwrite an existing destination, because that file is live captured data.
- It writes data/capture.seed.json, the record T-002's acceptance tests check: source path,
  source hash (db bytes then -wal bytes, if any), time, and per-table row counts.

Stop the old ingest server first, so the source is not being written while it is copied.
"""

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COUNT_SQL = REPO / "scripts" / "discovery" / "16_capture_seed_counts.sql"


def file_sha256(db: Path) -> str:
    h = hashlib.sha256(db.read_bytes())
    wal = db.with_name(db.name + "-wal")
    if wal.exists():
        h.update(wal.read_bytes())
    return h.hexdigest()


def row_counts(con: sqlite3.Connection) -> dict[str, int]:
    return {tbl: n for tbl, n in con.execute(COUNT_SQL.read_text())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", type=Path, required=True, help="old capture DB (leetcode-analyzer/data/leetcode.db)")
    ap.add_argument("--dest", type=Path, default=REPO / "data" / "capture.db")
    args = ap.parse_args()
    source, dest = args.source.resolve(), args.dest.resolve()
    record_path = dest.with_name(dest.stem + ".seed.json")

    if not source.is_file():
        sys.exit(f"source not found: {source}")
    if dest.exists() or record_path.exists():
        sys.exit(f"refusing to overwrite {dest} / {record_path}: it may hold live captured data")

    before = file_sha256(source)
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dst = sqlite3.connect(dest)
    src.backup(dst)
    dst.execute("PRAGMA journal_mode = WAL")  # same mode the ingest server uses

    if (check := dst.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
        sys.exit(f"integrity check failed on the copy: {check}")
    src_counts, dst_counts = row_counts(src), row_counts(dst)
    src.close()
    dst.close()
    if src_counts != dst_counts:
        sys.exit(f"row counts differ: source {src_counts} vs copy {dst_counts}")
    if file_sha256(source) != before:
        sys.exit("the source file changed while copying — is the old server still running?")

    record = {
        "source_path": str(source),
        "source_sha256": before,
        "seeded_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "row_counts": src_counts,
    }
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    print(f"seeded {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
