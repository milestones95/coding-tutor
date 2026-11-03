"""Extension-analysis fence — architecture §4.3 #3, §4.4, D-011. Tester-owned; kept for the life of
the project (`/test write T-004`, 2026-11-03).

The capture DB still holds the old extension analyzer's output: the `attempts` and
`attempt_gaps` tables and `sessions.analysis_status` / `analysis_error`. It is a model's
prediction, not data and not a label, so nothing in `src/tutor/` or `prompts/` may reference it.

`attempts` is also an ordinary English word (retry attempts), so the bare word is matched only
where it names a table: after FROM/JOIN/INTO/UPDATE/TABLE, or as a quoted identifier.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOTS = [REPO / "src" / "tutor", REPO / "prompts"]

PATTERNS = [
    re.compile(r"(?i)\b(from|join|into|update|table)\s+[\"'`\[]?attempts\b"),
    re.compile(r"""["'`]attempts["'`]"""),
    re.compile(r"\battempt_gaps\b"),
    re.compile(r"\banalysis_(status|error)\b"),
]


def _files():
    for root in ROOTS:
        if root.exists():
            yield from (p for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in {".py", ".sql", ".md", ".json"})


def test_nothing_references_the_extension_analyzer_output():
    hits = []
    for f in _files():
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if any(p.search(line) for p in PATTERNS):
                hits.append(f"{f.relative_to(REPO)}:{n}: {line.strip()}")
    assert not hits, "references the old extension analyzer's tables/columns:\n" + "\n".join(hits)


def test_the_fence_catches_what_it_should():
    """Grade the fence: hand-made lines whose right answer is known."""
    caught = ["SELECT * FROM attempts", "join attempts a on a.session_id = s.id", 'con.execute("attempts")',
              "SELECT gap FROM attempt_gaps", "s.analysis_status", "WHERE analysis_error IS NULL"]
    allowed = ["max_transient_retries attempts before giving up", "# two attempts at the same problem",
               "for attempt in range(3):", "SELECT * FROM sessions"]
    assert all(any(p.search(x) for p in PATTERNS) for x in caught)
    assert not any(any(p.search(x) for p in PATTERNS) for x in allowed)
