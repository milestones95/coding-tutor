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
WANT = {("timeline", "dev"): "dev-v4", ("failure", "dev"): "dev-v3", ("algorithm", "dev"): "dev-v2",
        ("timeline", "test"): "test-v2", ("failure", "test"): "test-v2", ("algorithm", "test"): "test-v2"}


def _rows(path):
    return [json.loads(x) for x in (REPO / path).read_text().splitlines() if x.strip()]


def _digest(row):
    r = {k: v for k, v in row.items() if k != "dataset_version"}
    return hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def test_every_v1_case_is_kept_byte_for_byte_in_its_split():
    changed = []
    for path, cases in DIGESTS.items():
        now = {r["case_id"]: _digest(r) for r in _rows(path)}
        changed += [f"{path}:{cid}" for cid, h in cases.items() if now.get(cid) != h]
    assert not changed, f"{len(changed)} v1 case(s) moved or changed"


def test_v1_cases_come_first_and_new_ones_follow_with_the_next_ids():
    for path, cases in DIGESTS.items():
        ids = [r["case_id"] for r in _rows(path)]
        assert ids[:len(cases)] == sorted(cases), f"{path}: v1 cases are not first, in order"
        assert ids == [f"{ids[0].rsplit('-', 1)[0]}-{i:03d}" for i in range(1, len(ids) + 1)], f"{path}: ids skip"


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
