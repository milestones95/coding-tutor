"""Look up LeetCode problem metadata in the capture DB, read-only, for a synthetic spec.

    uv run python .claude/skills/synthetic-spec/scripts/problem_meta.py coin-change
    uv run python .claude/skills/synthetic-spec/scripts/problem_meta.py "longest substring"

An exact slug prints one JSON object (the spec's `problem` block). Otherwise up to 8 title
matches are listed. The DB is opened mode=ro: this never writes capture data.
"""

import json
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parents[4] / "data" / "capture.db"


def main(query: str) -> int:
    con = sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True)
    row = con.execute("SELECT slug, title, difficulty, tags FROM problems WHERE slug = ?", (query,)).fetchone()
    if row:
        print(json.dumps({"slug": row[0], "title": row[1], "difficulty": row[2], "tags": json.loads(row[3])}))
        return 0
    rows = con.execute("SELECT slug, title, difficulty FROM problems WHERE title LIKE ? OR slug LIKE ? "
                       "ORDER BY length(title) LIMIT 8", (f"%{query}%", f"%{query}%")).fetchall()
    if not rows:
        print(f"no problem matches {query!r}", file=sys.stderr)
        return 1
    for slug, title, diff in rows:
        print(f"{slug}\t{title}\t{diff}")
    return 0


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
