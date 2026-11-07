"""Check synthetic-session specs against the eval contract, and print a coverage table.

Tester-owned (architecture §8.5, D-017). A spec is the label for one synthetic session, so a
spec that contradicts itself (say, an Accepted verdict with a failure type) would make the eval
grade models against an impossible answer. This catches that mechanically, before a human
reviews it and before any generation money is spent.

    uv run python evals/generate/check_specs.py evals/data/sessions/synthetic/specs.draft.jsonl
    uv run python evals/generate/check_specs.py specs.draft.jsonl specs.jsonl   # coverage across both
    uv run python evals/generate/check_specs.py --with-real specs.jsonl         # balance incl. real sessions

Exit 0 if every spec is valid, 1 otherwise. Warnings and skew lines don't fail; they flag what to fix
in the next specs.
"""

import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAPTURE_DB = REPO / "data" / "capture.db"

# LeetCode's verdict text, verbatim (architecture §4.3; D-019, D-022).
VERDICTS = {"Accepted", "Wrong Answer", "Time Limit Exceeded", "Memory Limit Exceeded", "Runtime Error",
            "Compile Error", "Output Limit Exceeded"}
FAILURE_TYPES = {"edge_case_missed", "wrong_approach", "too_slow", "implementation_bug", "did_not_finish", "none"}
ALGORITHMS = {"hash_map", "two_pointers", "sliding_window", "binary_search", "stack", "heap", "bfs",
              "dfs_backtracking", "dynamic_programming", "greedy", "intervals", "linked_list",
              "tree_traversal", "trie", "union_find", "graph_topological_sort", "bit_manipulation", "math"}
LANGUAGES = {"python3", "java", "cpp", "javascript", "typescript", "golang"}
SPLITS = {"dev", "test", "unassigned"}
KEYS = {"id", "split", "problem", "language", "duration_min", "runs", "verdict", "labels", "story", "key_facts"}


def _problem_db():
    if not CAPTURE_DB.exists():
        return None
    return sqlite3.connect(CAPTURE_DB.resolve().as_uri() + "?mode=ro", uri=True)


def check(spec: dict, db) -> tuple[list[str], list[str]]:
    """(errors, warnings) for one spec."""
    err, warn = [], []
    missing, extra = KEYS - spec.keys(), spec.keys() - KEYS
    if missing:
        return [f"missing keys: {sorted(missing)}"], []
    if extra:
        err.append(f"unknown keys: {sorted(extra)}")

    if not re.fullmatch(r"syn-\d{3}", str(spec["id"])):
        err.append("id must look like syn-001")
    if spec["split"] not in SPLITS:
        err.append(f"split must be one of {sorted(SPLITS)}")

    p = spec["problem"]
    if not isinstance(p, dict) or set(p) != {"slug", "title", "difficulty", "tags"}:
        err.append("problem must have exactly slug, title, difficulty, tags")
    elif db is not None:
        row = db.execute("SELECT title, difficulty, tags FROM problems WHERE slug = ?", (p["slug"],)).fetchone()
        if row is None:
            err.append(f"problem slug {p['slug']!r} is not a LeetCode problem in the capture DB")
        elif (row[0], row[1], json.loads(row[2])) != (p["title"], p["difficulty"], p["tags"]):
            err.append(f"problem metadata differs from LeetCode's; use problem_meta.py {p['slug']}")

    if spec["language"] not in LANGUAGES:
        err.append(f"language must be one of {sorted(LANGUAGES)}")
    d, runs = spec["duration_min"], spec["runs"]
    if not isinstance(d, (int, float)) or not 2 <= d <= 60:
        err.append("duration_min must be 2–60 (the token budget is measured for 60)")
    if not isinstance(runs, int) or not 0 <= runs <= 20:
        err.append("runs must be an integer 0–20")

    v = spec["verdict"]
    status = None
    if v is not None:
        if not isinstance(v, dict) or set(v) != {"status", "tests_passed", "tests_total"}:
            err.append("verdict must be null (never submitted) or {status, tests_passed, tests_total}")
        else:
            status, passed, total = v["status"], v["tests_passed"], v["tests_total"]
            if status not in VERDICTS:
                err.append(f"verdict.status must be LeetCode's exact text, one of {sorted(VERDICTS)}")
            if not (isinstance(passed, int) and isinstance(total, int) and 0 <= passed <= total and total >= 1):
                err.append("tests_passed / tests_total must be integers with 0 ≤ passed ≤ total, total ≥ 1")
            elif status == "Accepted" and passed != total:
                err.append("Accepted means every test passed")
            elif status != "Accepted" and passed == total:
                err.append("a failing verdict can't have every test passed")
            elif status == "Compile Error" and passed != 0:
                err.append("Compile Error runs no tests: tests_passed must be 0")

    labels = spec["labels"]
    ft = labels.get("failure_type") if isinstance(labels, dict) else None
    algos = labels.get("algorithms") if isinstance(labels, dict) else None
    if ft not in FAILURE_TYPES:
        err.append(f"labels.failure_type must be one of {sorted(FAILURE_TYPES)}")
    # The status → failure-type rules the pipeline applies (architecture §6.3): a spec that broke
    # them would label a case the rule-decided path can never get right.
    elif status == "Accepted" and ft != "none":
        err.append("Accepted ⇒ failure_type 'none'")
    elif status in ("Time Limit Exceeded", "Memory Limit Exceeded") and ft != "too_slow":
        err.append(f"{status} ⇒ failure_type 'too_slow' (rule-decided)")
    elif status not in ("Accepted",) and ft == "none":
        err.append("only an Accepted session has failure_type 'none'")
    elif status in ("Wrong Answer", "Runtime Error", "Compile Error", "Output Limit Exceeded") and ft == "too_slow":
        err.append(f"{status} isn't a too-slow failure")
    if not (isinstance(algos, list) and 1 <= len(algos) <= 2 and len(set(algos)) == len(algos)
            and set(algos) <= ALGORITHMS):
        err.append(f"labels.algorithms must be 1–2 distinct labels from {sorted(ALGORITHMS)}")

    story = spec["story"]
    if not isinstance(story, dict) or set(story) != {"approaches", "course_correction", "final_approach",
                                                      "on_track_algorithms"}:
        err.append("story must have exactly approaches, course_correction, final_approach, on_track_algorithms")
    else:
        ap = story["approaches"]
        if not (isinstance(ap, list) and ap and all(isinstance(a, str) and a.strip() for a in ap)):
            err.append("story.approaches must be a non-empty list of strings, in the order tried")
        if not (isinstance(story["final_approach"], str) and story["final_approach"].strip()):
            err.append("story.final_approach must be a non-empty string")
        cc = story["course_correction"]
        if not isinstance(cc, dict) or set(cc) != {"first_approach_on_track", "corrected", "at_min"}:
            err.append("course_correction must have first_approach_on_track, corrected, at_min (D-026)")
        else:
            on, corr, at = cc["first_approach_on_track"], cc["corrected"], cc["at_min"]
            if not isinstance(on, bool):
                err.append("first_approach_on_track must be true or false")
            elif on and (corr is not None or at is not None):
                err.append("first approach on track ⇒ corrected and at_min are null")
            elif not on and not isinstance(corr, bool):
                err.append("first approach off track ⇒ corrected is true or false")
            elif not on and corr and not (isinstance(at, (int, float)) and 0 < at < d):
                err.append("corrected ⇒ at_min is a minute inside the session")
            elif not on and corr is False and at is not None:
                err.append("not corrected ⇒ at_min is null")
            # What "on track" would have meant (D-039): labels only, never code, never a model input.
            ota = story["on_track_algorithms"]
            if on is True and ota is not None:
                err.append("first approach on track ⇒ on_track_algorithms is null (the approach used was on track)")
            elif on is False and not (isinstance(ota, list) and 1 <= len(ota) <= 2 and len(set(ota)) == len(ota)
                                      and set(ota) <= ALGORITHMS):
                err.append("first approach off track ⇒ on_track_algorithms is 1–2 labels from the algorithm list")
            elif on is False and isinstance(algos, list) and set(ota) == set(algos):
                warn.append("off track, yet the final code's algorithms equal the on-track ones: is one label wrong?")
            if ft == "wrong_approach" and not (on is False and corr is False):
                err.append("wrong_approach ⇒ the first approach was off track and never corrected")
            if on is True and isinstance(ap, list) and len(ap) > 1:
                warn.append("first approach on track but several approaches listed: is that a refinement, not a change?")
            if on is False and corr is True and isinstance(ap, list) and len(ap) < 2:
                warn.append("corrected, but only one approach listed")

    kf = spec["key_facts"]
    if not (isinstance(kf, list) and 1 <= len(kf) <= 5 and all(isinstance(k, str) and k.strip() for k in kf)):
        err.append("key_facts must be 1–5 short strings, each something visible in the session")
    if v is None and isinstance(runs, int) and runs == 0:
        warn.append("never submitted and never run: is there anything for the fields to read?")
    return err, warn


# Variety (human, 2026-11-07, D-040): no dimension may lean too far one way, or a metric ends up
# measuring the common case. Shares are over the whole dataset (with --with-real, real sessions
# count too). Checked once there are enough rows for a share to mean something.
BALANCE_MIN_ROWS = 8
MAX_SHARE = {"status": 0.35, "failure type": 0.30, "difficulty": 0.50, "time spent": 0.40, "algorithm": 0.20}
MIN_SHARE = {"difficulty": 0.15, "time spent": 0.10}
DIFFICULTIES = {"Easy", "Medium", "Hard"}
TIME_BUCKETS = ["under 10 min", "10–25 min", "25–45 min", "45–60 min"]


def time_bucket(minutes: float) -> str:
    return TIME_BUCKETS[0 if minutes < 10 else 1 if minutes < 25 else 2 if minutes < 45 else 3]


def spec_row(s: dict) -> dict:
    v = s["verdict"]
    cc = s["story"]["course_correction"]
    return {"source": "synthetic", "slug": s["problem"]["slug"],
            "status": v["status"] if v else "not submitted", "difficulty": s["problem"]["difficulty"],
            "time spent": time_bucket(s["duration_min"]), "failure type": s["labels"]["failure_type"],
            "algorithm": s["labels"]["algorithms"],
            "first approach": "on track" if cc["first_approach_on_track"]
            else ("corrected" if cc["corrected"] else "not corrected"),
            "near_miss": bool(v and v["status"] != "Accepted" and v["tests_passed"] / v["tests_total"] >= 0.9)}


def real_rows() -> list[dict]:
    """The frozen copy's real sessions, for status / difficulty / time balance. Their failure type
    and algorithms aren't labelled yet, so they don't count on those dimensions."""
    from tutor.capture.loader import CaptureLoader
    from tutor.config import load_settings
    from tutor.fields.deterministic import status, time_to_finish

    settings = load_settings()
    rows = []
    for x in CaptureLoader(settings.paths.eval_capture_db, mode="immutable", settings=settings,
                           run_id="check-specs").iter_sessions():
        st = status(x, settings=settings, run_id="check-specs")
        rows.append({"source": "real", "slug": x.problem.slug,
                     "status": st.leetcode_verdict or "not submitted", "difficulty": x.problem.difficulty,
                     "time spent": time_bucket(time_to_finish(x))})
    return rows


def coverage(rows: list[dict]) -> tuple[str, list[str]]:
    """A distribution table, and skew warnings once there are BALANCE_MIN_ROWS rows."""
    lines, skew = [], []
    n_real = sum(r["source"] == "real" for r in rows)
    lines.append(f"coverage over {len(rows)} sessions ({len(rows) - n_real} synthetic, {n_real} real)")
    universes = {"status": VERDICTS | {"not submitted"}, "failure type": FAILURE_TYPES,
                 "difficulty": DIFFICULTIES, "time spent": set(TIME_BUCKETS), "algorithm": None,
                 "first approach": {"on track", "corrected", "not corrected"}}
    for dim, universe in universes.items():
        have = [r for r in rows if dim in r]
        if not have:
            continue
        c = Counter(v for r in have for v in (r[dim] if isinstance(r[dim], list) else [r[dim]]))
        total = len(have)  # shares are per session (a session can carry 2 algorithm labels)
        order = TIME_BUCKETS if dim == "time spent" else sorted(universe or c)
        cells = ", ".join(f"{k} {c.get(k, 0)} ({c.get(k, 0) / total:.0%})" for k in order if universe or c.get(k))
        lines.append(f"  {dim} [{total}]: {cells}")
        gaps = sorted(k for k in (universe or []) if not c.get(k))
        if gaps:
            lines.append(f"    missing: {', '.join(gaps)}")
        if total >= BALANCE_MIN_ROWS:
            for k, n in c.items():
                if dim in MAX_SHARE and n / total > MAX_SHARE[dim]:
                    skew.append(f"{dim} leans on {k!r}: {n}/{total} = {n / total:.0%} (max {MAX_SHARE[dim]:.0%})")
            if dim in MIN_SHARE:
                for k in order:
                    if c.get(k, 0) / total < MIN_SHARE[dim]:
                        skew.append(f"{dim} has too few {k!r}: {c.get(k, 0)}/{total} (min {MIN_SHARE[dim]:.0%})")
    syn = [r for r in rows if r["source"] == "synthetic"]
    lines.append(f"  near-misses (failing with ≥ 90% tests passed): {sum(r['near_miss'] for r in syn)}")
    lines.append(f"  split: {dict(Counter(r.get('split', 'unassigned') for r in syn))}" if syn else "")
    # A real session repeating a problem is genuine practice; a synthetic spec reusing a problem
    # (real or synthetic) narrows the variety for nothing.
    syn_slugs = {r["slug"] for r in syn}
    repeats = [f"{s} ×{n}" for s, n in Counter(r["slug"] for r in rows).items() if n > 1 and s in syn_slugs]
    if repeats:
        skew.append(f"a synthetic spec reuses a problem: {', '.join(sorted(repeats))}")
    if len(rows) < BALANCE_MIN_ROWS:
        lines.append(f"  (balance is checked from {BALANCE_MIN_ROWS} sessions on)")
    return "\n".join(x for x in lines if x), skew


def main(argv: list[str]) -> int:
    with_real = "--with-real" in argv
    paths = [a for a in argv if a != "--with-real"]
    db = _problem_db()
    if db is None:
        print("warning: data/capture.db not found; problem metadata not checked", file=sys.stderr)
    specs, ids, bad = [], Counter(), 0
    for path in paths:
        for n, line in enumerate(Path(path).read_text().splitlines(), 1):
            if not line.strip():
                continue
            where = f"{path}:{n}"
            try:
                spec = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"ERROR {where}: not JSON ({e})")
                bad += 1
                continue
            errors, warnings = check(spec, db)
            ids[spec.get("id")] += 1
            for e in errors:
                print(f"ERROR {where} {spec.get('id')}: {e}")
            for w in warnings:
                print(f"warn  {where} {spec.get('id')}: {w}")
            if errors:
                bad += 1
            else:
                specs.append(spec)
    for sid, count in ids.items():
        if count > 1:
            print(f"ERROR id {sid} is used {count} times")
            bad += 1
    rows = [spec_row(s) | {"split": s["split"]} for s in specs] + (real_rows() if with_real else [])
    if rows:
        table, skew = coverage(rows)
        print(table)
        for w in skew:
            print(f"skew  {w}")
    print(f"{len(specs)} valid, {bad} invalid")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
