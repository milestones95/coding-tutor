"""Assemble the dataset from the approved specs and the human's real labels (T-021, T-040; arch §8.1).

Tester-owned. v1 (D-045) was a seeded draw inside each (status, real/synthetic) group. v2 (T-040,
D-072) never moves a session: every existing case is kept as written (only its dataset_version
changes) and new sessions are appended with the next case ids, in the split their spec names
(`"dev"` or `"test"`; `"unassigned"` is refused). `split()` stays for the record of how v1 was drawn. Writes evals/data/{failure,algorithm,timeline}/{dev,test}/cases.jsonl and
evals/data/manifest.json (hashes the frozen-dataset contract test checks). Prints counts only:
which sessions are in test is never printed (rule 2).

    uv run python evals/build/build_dataset.py
"""

import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # remap_failure_types (T-046)
DATA = REPO / "evals" / "data"
SEED = 20261107
TEST_SHARE = 9 / 28   # 19 dev / 9 test (D-045)
# A split's version bumps when any of its cases changes (rule 10). History: timeline/dev-v2 syn-003
# (D-063), timeline/dev-v3 + failure/dev-v2 Sort Colors (D-066). Dataset v2 (T-040, D-072) bumps all
# six files: new sessions in every test file, Merge Sorted Array's algorithm case in algorithm/dev.
# T-050 (rule 2) moves the 8 unsealed sessions to dev in every suite: dev-v5 / dev-v4 / dev-v3, test-v3.
# T-046 (D-079) remaps failure labels: failure dev-v5 (no test label changed, so failure test stays test-v3).
VERSIONS = {("timeline", "dev"): "dev-v5", ("failure", "dev"): "dev-v5", ("algorithm", "dev"): "dev-v3",
            ("timeline", "test"): "test-v3", ("failure", "test"): "test-v3", ("algorithm", "test"): "test-v3"}
# Test sessions whose failure details the human saw on 2026-11-17 (rule 2: "that case moves to dev and gets a
# replacement"; T-050). They leave every test file and are appended to dev with the next ids, labels unchanged.
# Remaining test cases keep their ids, so a test file's ids may skip where a moved case was.
MOVED = {"syn-009", "syn-013", "syn-018", "syn-023", "syn-025", "syn-027", "syn-029", "syn-030"}


def outcome(verdict, passed, total):
    """The timeline checklist's outcome, read from the verdict (a fact, rule 1; D-059)."""
    if verdict is None:
        return "not submitted"
    return f"{verdict}, {passed}/{total} tests passed" if total else verdict


def sessions():
    """(key, source, status, near_miss, labels, story, key_facts, session_ref) for every session."""
    sys.path.insert(0, str(REPO / "src"))
    from tutor.config import load_settings
    from tutor.capture.loader import CaptureLoader
    from tutor.fields.deterministic import status

    out = []
    for line in (DATA / "sessions" / "synthetic" / "specs.jsonl").read_text().splitlines():
        s = json.loads(line)
        v = s["verdict"]
        out.append({"key": s["id"], "source": "synthetic", "status": v["status"] if v else "not submitted",
                    "near_miss": bool(v and v["status"] != "Accepted" and v["tests_passed"] / v["tests_total"] >= 0.9),
                    "labels": s["labels"], "story": s["story"], "key_facts": s["key_facts"],
                    "outcome": outcome(v["status"], v["tests_passed"], v["tests_total"]) if v else outcome(None, None, None),
                    "session": {"synthetic_path": f"evals/data/sessions/synthetic/{s['id']}.json"}})
    settings = load_settings()
    loader = CaptureLoader(settings.paths.eval_capture_db, mode="immutable", settings=settings, run_id="build-dataset")
    for line in (DATA / "sessions" / "real" / "labels.jsonl").read_text().splitlines():
        r = json.loads(line)
        st = status(loader.load_session(r["capture_session_id"]), settings=settings, run_id="build-dataset")
        out.append({"key": r["capture_session_id"], "source": "real", "status": st.leetcode_verdict or "not submitted",
                    "near_miss": bool(st.tests_total and st.leetcode_verdict != "Accepted"
                                      and st.tests_passed / st.tests_total >= 0.9),
                    "labels": r["labels"], "story": r["story"], "key_facts": r["key_facts"],
                    "outcome": outcome(st.leetcode_verdict, st.tests_passed, st.tests_total),
                    "session": {"capture_session_id": r["capture_session_id"]}})
    return out


def split(rows):
    """Seeded and stratified. Each status gets ~1/3 of its sessions in test (at least one if it has
    two or more), and within a status the test picks keep the real/synthetic mix."""
    rng = random.Random(SEED)
    by_status = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["key"]):
        by_status[r["status"]].append(r)
    quota = {st: (max(1, round(len(g) / 3)) if len(g) >= 2 else 0) for st, g in by_status.items()}
    target = round(len(rows) * TEST_SHARE)
    while sum(quota.values()) > target:   # trim from the biggest statuses first
        st = max((s for s in quota if quota[s] > 1), key=lambda s: (len(by_status[s]), s))
        quota[st] -= 1
    while sum(quota.values()) < target:
        st = max(quota, key=lambda s: (len(by_status[s]) - 3 * quota[s], s))
        quota[st] += 1
    test_keys = set()
    for st, g in sorted(by_status.items()):
        real = [r for r in g if r["source"] == "real"]
        syn = [r for r in g if r["source"] == "synthetic"]
        rng.shuffle(real)
        rng.shuffle(syn)
        n_real = round(quota[st] * len(real) / len(g)) if g else 0
        n_real = min(n_real, len(real), quota[st])
        picks = real[:n_real] + syn[: quota[st] - n_real]
        test_keys |= {r["key"] for r in picks}
    return {r["key"]: ("test" if r["key"] in test_keys else "dev") for r in rows}


def _ref(session: dict) -> str:
    return json.dumps(session, sort_keys=True)


def _expected(suite, r):
    if suite == "failure":
        return {"failure_type": r["labels"]["failure_type"], "key_facts": r["key_facts"]}
    if suite == "algorithm":
        return {"labels": r["labels"]["algorithms"]}
    return {"checklist": {"approaches": r["story"]["approaches"],
                          "course_correction": r["story"]["course_correction"],
                          "final_approach": r["story"]["final_approach"],
                          "outcome": r["outcome"]},
            "key_facts": r["key_facts"]}


def _existing():
    """(suite, split) → the committed case rows, in file order."""
    out = {}
    for suite in ("failure", "algorithm", "timeline"):
        for sp in ("dev", "test"):
            path = DATA / suite / sp / "cases.jsonl"
            out[(suite, sp)] = [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
    return out


def pinned_split(rows, existing, spec_splits):
    """A session already in the dataset keeps its split (the failure suite holds every session); a new
    one takes its spec's explicit split. Anything else is an error, never a guess."""
    where = {}
    for (suite, sp), cases in existing.items():
        for c in cases:
            where[_ref(c["session"])] = sp
    out = {}
    for r in rows:
        ref = _ref(r["session"])
        if r["key"] in MOVED:
            out[r["key"]] = "dev"
        elif ref in where:
            out[r["key"]] = where[ref]
        elif r["source"] == "synthetic" and spec_splits.get(r["key"]) in ("dev", "test"):
            out[r["key"]] = spec_splits[r["key"]]
        else:
            raise SystemExit(f"{r['key']}: a new session needs \"split\": \"dev\" or \"test\" in its spec")
    return out


def main():
    rows = sessions()
    existing = _existing()
    spec_splits = {json.loads(x)["id"]: json.loads(x)["split"]
                   for x in (DATA / "sessions" / "synthetic" / "specs.jsonl").read_text().splitlines() if x.strip()}
    where = pinned_split(rows, existing, spec_splits)
    by_ref = {_ref(r["session"]): r for r in rows}
    written, added = {}, Counter()
    for suite in ("failure", "algorithm", "timeline"):
        for sp in ("dev", "test"):
            version = VERSIONS[(suite, sp)]
            cases, have = [], set()
            for c in existing[(suite, sp)]:
                r = by_ref[_ref(c["session"])]
                if where[r["key"]] != sp:
                    continue   # moved out of this split (T-050); it is appended to the other one below
                want = _expected(suite, r)
                if c["expected"] != want:
                    # The one allowed change: a failure label remapped by D-079's table (T-046), from status alone.
                    from remap_failure_types import VERDICT_STATUS, remap
                    old = c["expected"]["failure_type"] if suite == "failure" else None
                    if not (old and {**c["expected"], "failure_type": want["failure_type"]} == want
                            and remap(old, VERDICT_STATUS[r["status"]]) == want["failure_type"]):
                        raise SystemExit(f"{c['case_id']}: its label changed; that needs its own reason and version")
                    c = {**c, "expected": want}
                cases.append({**c, "dataset_version": version})
                have.add(_ref(c["session"]))
            for r in sorted((r for r in rows if where[r["key"]] == sp), key=lambda r: r["key"]):
                if _ref(r["session"]) in have:
                    continue
                if suite == "algorithm" and not r["labels"]["algorithms"]:
                    continue  # no label in the fixed list applies (D-050)
                tags = (["near_miss"] if r["near_miss"] else []) + (["rule_decided"] if suite == "failure" and r["status"] in
                        ("Accepted", "Time Limit Exceeded", "Memory Limit Exceeded") else [])
                nxt = max((int(c["case_id"].rsplit("-", 1)[1]) for c in cases), default=0) + 1
                cases.append({"case_id": f"{suite}-{sp}-{nxt:03d}", "suite": suite, "split": sp,
                              "dataset_version": version, "source": r["source"], "session": r["session"],
                              "expected": _expected(suite, r), "label_source": "human_written", "tags": tags, "notes": ""})
                added[(suite, sp)] += 1
            path = DATA / suite / sp / "cases.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases))
            written[str(path.relative_to(REPO))] = len(cases)
    manifest = {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in sorted(written)}
    for p in ("evals/data/sessions/synthetic/specs.jsonl", "evals/data/sessions/real/labels.jsonl",
              "evals/data/calibration/timeline/v1.jsonl",   # the human's judge grades are frozen too (D-063)
              "evals/data/calibration/failure_explanation/v1.jsonl",
              "evals/data/v1_case_digests.json",            # what dataset v2 must keep (T-040)
              "evals/data/split_v2.json"):                  # every session's split before T-050's move
        manifest[p] = hashlib.sha256((REPO / p).read_bytes()).hexdigest()
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # counts only
    print("sessions per split:", dict(Counter(where.values())))
    by = Counter((where[r["key"]], r["status"], r["source"]) for r in rows)
    for st in sorted({r["status"] for r in rows}):
        for src in ("real", "synthetic"):
            d, t = by[("dev", st, src)], by[("test", st, src)]
            if d or t:
                print(f"  {st:22} {src:9}  dev {d}  test {t}")
    print("cases written:", written)
    print("cases added:", {f"{s}/{sp}": n for (s, sp), n in sorted(added.items())})


if __name__ == "__main__":
    main()
