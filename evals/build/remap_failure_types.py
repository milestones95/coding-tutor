"""Failure types v2 (D-079, T-046): remap every human failure label from the session's status alone.

Tester-owned. The table below is the whole rule; nothing reads the session's code or story, so the test
split's labels can be remapped without anyone looking at a test case (counts only are printed).

    uv run python evals/build/remap_failure_types.py          # rewrite specs.jsonl and real/labels.jsonl
    uv run python evals/build/build_dataset.py                # then rebuild the cases files

| status                                   | old label            | new label            |
|------------------------------------------|----------------------|----------------------|
| passed                                   | none                 | none                 |
| failed_too_slow (TLE, MLE)               | too_slow             | too_slow             |
| not_submitted                            | any                  | did_not_finish       |
| unknown (no verdict captured)            | any                  | unknown              |
| WA, RE, OLE                              | edge_case_missed     | implementation_bug   |
| WA, RE, OLE                              | wrong_approach / implementation_bug | unchanged |

Anything else (a submitted session labelled did_not_finish, a WA labelled too_slow, …) is refused: it
needs the human's judgment, not a rule.
"""

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "evals" / "data"

# The failure types after D-079. `edge_case_missed` is gone; `unknown` is new.
FAILURE_TYPES_V2 = frozenset({"none", "too_slow", "wrong_approach", "implementation_bug", "did_not_finish", "unknown"})
# Statuses where the LLM decides (D-079): the only two answers it may give.
LLM_DECIDED = frozenset({"failed_wrong_answer", "failed_runtime_error", "failed_output_limit"})
LLM_TYPES = frozenset({"wrong_approach", "implementation_bug"})
# The status → label rules; the LLM never sees these statuses.
RULES = {"passed": "none", "failed_too_slow": "too_slow", "not_submitted": "did_not_finish", "unknown": "unknown"}

# LeetCode verdict text (as specs and the dataset builder carry it) → Status value.
VERDICT_STATUS = {"Accepted": "passed", "Wrong Answer": "failed_wrong_answer",
                  "Time Limit Exceeded": "failed_too_slow", "Memory Limit Exceeded": "failed_too_slow",
                  "Runtime Error": "failed_runtime_error", "Compile Error": "failed_runtime_error",
                  "Output Limit Exceeded": "failed_output_limit", "not submitted": "not_submitted"}


class RemapError(ValueError):
    """A label the D-079 table has no rule for: the human decides it."""


def remap(old: str, status: str) -> str:
    """The D-079 label for a session with this status whose old label was `old`."""
    if status in ("not_submitted", "unknown"):
        return RULES[status]
    if status in ("passed", "failed_too_slow"):
        if old != RULES[status]:
            raise RemapError(f"status {status} with label {old!r}: the rule says {RULES[status]!r}")
        return old
    if status in LLM_DECIDED:
        if old == "edge_case_missed":
            return "implementation_bug"
        if old in LLM_TYPES:
            return old
        raise RemapError(f"status {status} with label {old!r}: only wrong_approach or implementation_bug")
    raise RemapError(f"unknown status {status!r}")


def _real_statuses() -> dict[str, str]:
    sys.path.insert(0, str(REPO / "src"))
    from tutor.capture.loader import CaptureLoader
    from tutor.config import load_settings
    from tutor.fields.deterministic import status

    settings = load_settings()
    loader = CaptureLoader(settings.paths.eval_capture_db, mode="immutable", settings=settings, run_id="remap-failure")
    out = {}
    for line in (DATA / "sessions" / "real" / "labels.jsonl").read_text().splitlines():
        sid = json.loads(line)["capture_session_id"]
        out[sid] = status(loader.load_session(sid), settings=settings, run_id="remap-failure").status.value
    return out


def _rewrite(path: Path, status_of) -> Counter:
    """Rewrite one JSONL label file in place, changing only `labels.failure_type`. Returns change counts
    keyed by (split, old → new); the split comes from where the session sits in the dataset."""
    where = json.loads((DATA / "split_v2.json").read_text())   # T-050 moved 8 sessions to dev after this snapshot
    moved = {f"evals/data/sessions/synthetic/{s}.json" for s in
             ("syn-009", "syn-013", "syn-018", "syn-023", "syn-025", "syn-027", "syn-029", "syn-030")}
    changes, lines = Counter(), []
    for line in path.read_text().splitlines():
        row = json.loads(line)
        key, st = status_of(row)
        old = row["labels"]["failure_type"]
        new = remap(old, st)
        if new != old:
            sp = "dev" if key in moved else where[key]
            changes[(sp, f"{old} → {new}")] += 1
            # replace the one field textually, so the rest of the line stays byte-identical
            a, b = f'"failure_type": "{old}"', f'"failure_type": "{new}"'
            assert line.count(a) == 1, f"{key}: can't place the label"
            line = line.replace(a, b)
        lines.append(line)
    path.write_text("".join(x + "\n" for x in lines))
    return changes


def main() -> int:
    real = _real_statuses()

    def spec_status(row):
        v = row["verdict"]
        return f"evals/data/sessions/synthetic/{row['id']}.json", VERDICT_STATUS[v["status"] if v else "not submitted"]

    def real_status(row):
        return row["capture_session_id"], real[row["capture_session_id"]]

    changes = _rewrite(DATA / "sessions" / "synthetic" / "specs.jsonl", spec_status)
    changes += _rewrite(DATA / "sessions" / "real" / "labels.jsonl", real_status)
    # counts only: which test sessions changed is never printed (rule 2)
    for sp in ("dev", "test"):
        total = sum(n for (s, _), n in changes.items() if s == sp)
        print(f"{sp}: {total} label(s) changed", {k: n for (s, k), n in sorted(changes.items()) if s == sp})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
