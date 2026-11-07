"""Assemble dataset v1 from the approved specs and the human's real labels (T-021; arch §8.1; D-045).

Tester-owned. Deterministic: a seeded draw inside each (status, real/synthetic) group, so re-running
gives the same split. Writes evals/data/{failure,algorithm}/{dev,test}/cases.jsonl and
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
DATA = REPO / "evals" / "data"
SEED = 20261107
TEST_SHARE = 9 / 28   # 19 dev / 9 test (D-045)


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


def main():
    rows = sessions()
    where = split(rows)
    written = {}
    for suite in ("failure", "algorithm"):
        for sp in ("dev", "test"):
            cases = []
            for r in sorted((r for r in rows if where[r["key"]] == sp), key=lambda r: r["key"]):
                if suite == "algorithm" and not r["labels"]["algorithms"]:
                    continue  # no label in the fixed list applies (D-050)
                expected = ({"failure_type": r["labels"]["failure_type"], "key_facts": r["key_facts"]} if suite == "failure"
                            else {"labels": r["labels"]["algorithms"]})
                tags = (["near_miss"] if r["near_miss"] else []) + (["rule_decided"] if suite == "failure" and r["status"] in
                        ("Accepted", "Time Limit Exceeded", "Memory Limit Exceeded") else [])
                cases.append({"case_id": f"{suite}-{sp}-{len(cases) + 1:03d}", "suite": suite, "split": sp,
                              "dataset_version": f"{sp}-v1", "source": r["source"], "session": r["session"],
                              "expected": expected, "label_source": "human_written", "tags": tags, "notes": ""})
            path = DATA / suite / sp / "cases.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases))
            written[str(path.relative_to(REPO))] = len(cases)
    manifest = {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in sorted(written)}
    for p in ("evals/data/sessions/synthetic/specs.jsonl", "evals/data/sessions/real/labels.jsonl"):
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


if __name__ == "__main__":
    main()
