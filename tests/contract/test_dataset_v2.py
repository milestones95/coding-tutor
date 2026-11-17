"""Contract: dataset v2 added sessions without moving or changing any v1 case (T-040, D-072; rules 2
and 10). Tester-owned (`/test write T-040`, 2026-11-14). Kept for the project's life.

`evals/data/v1_case_digests.json` holds, per cases file, each v1 case id and the sha256 of its row
without `dataset_version`. It was written from the committed v1 files before the rebuild and is
itself frozen in the manifest. Test cases are only counted and hashed here, never printed.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "evals" / "data"
DIGESTS = json.loads((DATA / "v1_case_digests.json").read_text())
WANT = {("timeline", "dev"): "dev-v5", ("failure", "dev"): "dev-v5", ("algorithm", "dev"): "dev-v3",
        ("timeline", "test"): "test-v3", ("failure", "test"): "test-v3", ("algorithm", "test"): "test-v3"}
# T-050 (rule 2, 2026-11-17): v1 test sessions the human unsealed; they moved to dev with their labels.
# Every other v1 case must still be byte-for-byte where it was.
MOVED_V1 = {"evals/data/sessions/synthetic/syn-009.json", "evals/data/sessions/synthetic/syn-013.json",
            "evals/data/sessions/synthetic/syn-018.json", "evals/data/sessions/synthetic/syn-023.json"}


def _rows(path):
    return [json.loads(x) for x in (REPO / path).read_text().splitlines() if x.strip()]


# T-046 (D-079): a v1 failure label may differ only by the remap table. These are the old labels that
# remap to each new one, so the test can rebuild the v1 row and check its digest.
PREIMAGES = {"implementation_bug": ["edge_case_missed"],
             "did_not_finish": ["wrong_approach", "implementation_bug", "edge_case_missed"]}


def _remapped_from_v1(row, h):
    """True when `row` equals its frozen v1 row except for a failure label D-079 remapped."""
    ft = row["expected"].get("failure_type")
    for old in PREIMAGES.get(ft, []):
        if _digest({**row, "expected": {**row["expected"], "failure_type": old}}) == h:
            return True
    return False


def _digest(row):
    r = {k: v for k, v in row.items() if k != "dataset_version"}
    return hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def test_every_v1_case_is_kept_byte_for_byte_in_its_split():
    for path, cases in DIGESTS.items():
        rows = {r["case_id"]: r for r in _rows(path)}
        changed = [cid for cid, h in cases.items() if cid in rows and _digest(rows[cid]) != h
                   and not ("/failure/" in path and _remapped_from_v1(rows[cid], h))]
        assert not changed, f"{path}: {len(changed)} v1 case(s) changed"
        gone = [cid for cid in cases if cid not in rows]
        if "/dev/" in path:
            assert not gone, f"{path}: {len(gone)} v1 dev case(s) missing"
        else:
            # A v1 test case may be missing only because T-050 moved its session: exactly as many v1 cases
            # left this test file as MOVED_V1 sessions now sit in the same suite's dev file.
            dev = {r["session"].get("synthetic_path") for r in _rows(path.replace("/test/", "/dev/"))}
            assert len(gone) == len(MOVED_V1 & dev), f"{path}: {len(gone)} v1 test case(s) left test"


def test_v1_cases_come_first_and_new_ones_follow_with_the_next_ids():
    """Dev files never skip an id. A test file may skip only where T-050 moved a case out; ids still increase."""
    for path, cases in DIGESTS.items():
        ids = [r["case_id"] for r in _rows(path)]
        kept = [c for c in sorted(cases) if c in ids]
        assert ids[:len(kept)] == kept, f"{path}: v1 cases are not first, in order"
        nums = [int(i.rsplit("-", 1)[1]) for i in ids]
        assert nums == sorted(set(nums)), f"{path}: ids repeat or go backwards"
        if "/dev/" in path:
            assert nums == list(range(1, len(nums) + 1)), f"{path}: ids skip"


def test_every_file_carries_its_v2_version():
    for (suite, sp), version in WANT.items():
        rows = _rows(f"evals/data/{suite}/{sp}/cases.jsonl")
        assert rows and {r["dataset_version"] for r in rows} == {version}, f"{suite}/{sp}"


def test_no_session_is_in_both_splits_and_every_suite_agrees_on_the_split():
    where = {}
    for (suite, sp) in WANT:
        for r in _rows(f"evals/data/{suite}/{sp}/cases.jsonl"):
            ref = json.dumps(r["session"], sort_keys=True)
            assert where.setdefault(ref, sp) == sp, "a session sits in different splits across suites"


def test_the_test_split_holds_at_least_two_course_corrected_sessions():
    """The T-030 finding: v1's test split had none, so M7 couldn't measure correction reporting."""
    corrected = sum(1 for r in _rows("evals/data/timeline/test/cases.jsonl")
                    if r["expected"]["checklist"]["course_correction"].get("corrected") is True)
    assert corrected >= 2


def test_every_approved_spec_is_in_the_dataset_once():
    specs = [json.loads(x)["id"] for x in (DATA / "sessions/synthetic/specs.jsonl").read_text().splitlines() if x.strip()]
    refs = Counter(r["session"].get("synthetic_path") for r in _rows("evals/data/failure/dev/cases.jsonl")
                   + _rows("evals/data/failure/test/cases.jsonl"))
    missing = [s for s in specs if refs[f"evals/data/sessions/synthetic/{s}.json"] != 1]
    assert not missing, f"{len(missing)} spec(s) not in the failure suite exactly once"
