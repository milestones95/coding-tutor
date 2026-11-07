"""Deterministic checks for a synthetic session file (architecture §8.5; D-043, D-048).

Tester-owned (T-017). The human writes each session (D-048); these checks make sure it is a
faithful, label-free input before it becomes eval data:

    uv run python evals/generate/checks.py            # every synthetic session
    uv run python evals/generate/checks.py syn-005    # one session

A rule a human has knowingly accepted for one session is listed under `waivers` in that session's
`<id>.meta.json` (e.g. "duration"); it is reported as waived, never silently skipped.
Exit 0 if every session passes (waivers aside), 1 otherwise.
"""

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SYN = REPO / "evals" / "data" / "sessions" / "synthetic"
RUN_STATUSES = {"Passed sample tests", "Wrong Answer (sample tests)", "Runtime Error", "Time Limit Exceeded"}
FAILURE_WORDS = ["edge case", "wrong approach", "too slow", "implementation bug", "did not finish"]
ALGO_WORDS = {  # label → words that name it in prose (code identifiers like `stack` or `heapq` are fine)
    "hash_map": ["hash map", "hashmap"], "two_pointers": ["two pointer", "two-pointer"],
    "sliding_window": ["sliding window"], "binary_search": ["binary search"],
    "stack": ["monotonic stack"], "heap": ["priority queue", "min-heap", "max-heap", "min heap", "max heap"],
    "bfs": ["breadth-first", "breadth first"], "dfs_backtracking": ["depth-first", "depth first", "backtrack"],
    "dynamic_programming": ["dynamic programming", " dp ", "memoiz", "memois"], "greedy": ["greedy"],
    "intervals": ["interval merging"], "linked_list": ["linked list"], "tree_traversal": ["tree traversal"],
    "trie": ["prefix tree"], "union_find": ["union-find", "union find", "disjoint set"],
    "graph_topological_sort": ["topological"], "bit_manipulation": ["bit manipulation"], "math": [],
    "prefix_sum": ["prefix sum", "prefix product"],
}
GIVEAWAY = re.compile(r"(?i)\b(bug|should be|should use|instead of|too slow|o\(n\^?2\)|o\(n²\)|overflow check|"
                      r"brute[- ]force|wrong approach|edge case)\b")


# LeetCode's own editor boilerplate ("# Definition for singly-linked list.", the commented-out
# ListNode/TreeNode classes, "# Your LRUCache object will be instantiated...") is not the author's.
BOILERPLATE = re.compile(r"^(Definition for |class \w+|def __init__|self\.\w+ = |Your \w+ object will be|obj = |param_\d|obj\.)")


def _comments(code: str) -> list[str]:
    out = []
    for line in code.splitlines():
        if "#" in line:
            c = line.split("#", 1)[1].strip()
            if not BOILERPLATE.match(c):
                out.append(c)
    return out


def check_session(raw: dict, spec: dict, final_code: str, waivers: set[str] = frozenset()) -> tuple[list[str], list[str]]:
    """(problems, waived) for one session dict against its spec and the human's final code."""
    from pydantic import ValidationError

    from tutor.condense import CondenseBudgetError, condense, elapsed_min, session_times
    from tutor.models import Session

    problems: list[tuple[str, str]] = []  # (rule, message)
    try:
        s = Session.model_validate(raw)
    except ValidationError as e:
        return [f"schema: {err['loc']}: {err['msg']}" for err in e.errors()[:5]], []

    if s.session_id != spec["id"]:
        problems.append(("id", f"session_id {s.session_id!r} isn't the spec id {spec['id']!r}"))
    p = spec["problem"]
    if (s.problem.slug, s.problem.title, s.problem.difficulty, s.problem.tags) != (
            p["slug"], p["title"], p["difficulty"], p["tags"]):
        problems.append(("problem", "problem block differs from the spec"))
    if not s.submit_capture_reliable:
        problems.append(("reliable", "submit_capture_reliable must be true for a synthetic session"))

    # 1. snapshots: order, spacing, no repeats, language
    snaps = s.snapshots
    if [x.ts for x in snaps] != sorted(x.ts for x in snaps):
        problems.append(("order", "snapshots are not in time order"))
    if any((b.ts - a.ts).total_seconds() < 5 for a, b in zip(snaps, snaps[1:])):
        problems.append(("spacing", "two snapshots are under 5 s apart"))
    if any(a.code == b.code for a, b in zip(snaps, snaps[1:])):
        problems.append(("repeat", "two consecutive snapshots are identical"))
    if any(x.language != "python3" for x in snaps):
        problems.append(("language", "every snapshot must be python3 (D-042)"))
    timed = [e.ts for e in s.events if e.ts is not None]
    if timed != sorted(timed):
        problems.append(("order", "events are not in time order"))

    # 2. shape within ±20% of the spec
    t0, t_end = session_times(s)
    minutes = elapsed_min(t_end, t0)
    if abs(minutes - spec["duration_min"]) > 0.2 * spec["duration_min"]:
        problems.append(("duration", f"{minutes} min vs spec {spec['duration_min']} (±20%)"))
    runs = [e for e in s.events if e.kind == "run"]
    if abs(len(runs) - spec["runs"]) > max(1, round(0.2 * spec["runs"])):
        problems.append(("runs", f"{len(runs)} runs vs spec {spec['runs']}"))
    bad = sorted({e.status for e in runs} - RUN_STATUSES)
    if bad:
        problems.append(("run_status", f"run status isn't LeetCode's text: {bad}"))

    # 3. final code and the submit are facts from the human and the spec
    if snaps[-1].code != final_code:
        problems.append(("final_code", "the last snapshot isn't exactly final_code/<id>.py"))
    subs = [e for e in s.events if e.kind == "submit"]
    v = spec["verdict"]
    if v is None:
        if subs:
            problems.append(("submit", "the spec says never submitted, but the file has a submit"))
    elif len(subs) != 1:
        problems.append(("submit", f"expected exactly one submit, found {len(subs)}"))
    else:
        f = subs[0]
        if (f.verdict, f.tests_passed, f.tests_total) != (v["status"], v["tests_passed"], v["tests_total"]):
            problems.append(("submit", f"submit {f.verdict} {f.tests_passed}/{f.tests_total} ≠ spec "
                                       f"{v['status']} {v['tests_passed']}/{v['tests_total']}"))
        if f.source != "capture_submit" or s.events[-1] is not f:
            problems.append(("submit", "the submit must be the last event, with source capture_submit"))

    # 4. leak check: comments and run output may not name a label or quote a key fact
    texts = [c for x in snaps for c in _comments(x.code)] + [e.error_detail for e in s.events if e.error_detail]
    lowered = [" " + t.lower() + " " for t in texts]
    names = list(FAILURE_WORDS)
    for label in spec["labels"]["algorithms"] + (spec["story"]["on_track_algorithms"] or []):
        names += ALGO_WORDS.get(label, [])
    for name in names:
        if any(name in t for t in lowered):
            problems.append(("leak", f"a comment or run output names a label: {name.strip()!r}"))
    for kf in spec["key_facts"]:
        if any(kf.lower() in t for t in lowered):
            problems.append(("leak", f"a comment or run output quotes a key fact: {kf[:40]!r}"))
    for c in (c for x in snaps for c in _comments(x.code)):
        if GIVEAWAY.search(c):
            problems.append(("leak", f"a comment gives the answer away: {c[:60]!r}"))

    # 5. it condenses within the token budget
    try:
        condense(s)
    except CondenseBudgetError as e:
        problems.append(("budget", str(e)))

    seen, out, waived = set(), [], []
    for rule, msg in problems:
        if msg in seen:
            continue
        seen.add(msg)
        (waived if rule in waivers else out).append(f"{rule}: {msg}")
    return out, waived


def main(ids: list[str]) -> int:
    specs = {json.loads(row)["id"]: json.loads(row) for row in (SYN / "specs.jsonl").read_text().splitlines() if row.strip()}
    failed = 0
    for sid in ids or sorted(specs):
        path = SYN / f"{sid}.json"
        if not path.exists():
            print(f"MISSING {sid}: no {path.name}")
            failed += 1
            continue
        meta_path = SYN / f"{sid}.meta.json"
        waivers = set(json.loads(meta_path.read_text()).get("waivers", [])) if meta_path.exists() else set()
        problems, waived = check_session(json.loads(path.read_text()), specs[sid],
                                         (SYN / "final_code" / f"{sid}.py").read_text(), waivers)
        status = "FAIL" if problems else "ok"
        print(f"{status:4} {sid}" + (f"  (waived: {'; '.join(waived)})" if waived else ""))
        for p in problems:
            print(f"     - {p}")
        failed += bool(problems)
    print(f"{len(ids or specs) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO / "src"))
    sys.exit(main(sys.argv[1:]))
