"""Contract: the eval dataset is frozen — CLAUDE.md rule 10; architecture §8.1. Tester-owned
(T-021, 2026-11-07). Kept for the project's life.

Every cases file, the synthetic specs and the real labels must match the hashes in
evals/data/manifest.json. A change means a new dataset_version and a written reason in the task,
then `uv run python evals/build/build_dataset.py` to rewrite the manifest, never an edit to make
an eval pass. Also checks that the dev files load through the real loader and never mention a
test case.
"""

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "evals" / "data" / "manifest.json"


def test_every_frozen_file_matches_its_hash():
    manifest = json.loads(MANIFEST.read_text())
    changed = [p for p, h in manifest.items() if hashlib.sha256((REPO / p).read_bytes()).hexdigest() != h]
    assert not changed, f"frozen dataset files changed without a new dataset_version: {changed}"


def test_every_cases_file_is_in_the_manifest():
    manifest = json.loads(MANIFEST.read_text())
    files = {str(p.relative_to(REPO)) for p in (REPO / "evals" / "data").glob("*/*/cases.jsonl")}
    assert files <= manifest.keys(), f"cases files missing from the manifest: {sorted(files - manifest.keys())}"


def test_dev_cases_load_and_never_reference_a_test_session():
    from tutor.evals.cases import load_cases

    for suite in ("failure", "algorithm", "timeline"):
        dev = load_cases(suite, "dev")
        want = {"timeline": "dev-v3", "failure": "dev-v2"}.get(suite, "dev-v1")   # D-063 syn-003; D-066 Sort Colors
        assert dev and all(c.split == "dev" and c.dataset_version == want for c in dev)
    dev_refs = {json.dumps(json.loads(row)["session"], sort_keys=True)
                for s in ("failure", "algorithm", "timeline")
                for row in (REPO / "evals" / "data" / s / "dev" / "cases.jsonl").read_text().splitlines()}
    test_refs = {json.dumps(json.loads(row)["session"], sort_keys=True)
                 for s in ("failure", "algorithm", "timeline")
                 for row in (REPO / "evals" / "data" / s / "test" / "cases.jsonl").read_text().splitlines()}
    assert not dev_refs & test_refs, "a session appears in both dev and test"
