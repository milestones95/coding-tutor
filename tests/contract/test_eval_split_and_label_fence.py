"""Contract: the test-split lock and the label fence — architecture §8.2, §4.3 #1; CLAUDE.md rules 1
and 2. Tester-owned (`/test write T-016`, 2026-11-07; interfaces D-049). Kept for the project's life.

- The sealed test split can only be read with `milestone=<id>` listed in `evals/test_approvals.json`
  (human-written). The lock is in the loader, checked on the resolved path, not in the caller.
- No module under `src/tutor/` outside `tutor/evals/` refers to `evals/data` or imports
  `tutor.evals.cases`, so a field function can't reach a label.
"""

import ast
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CASE = {"case_id": "algorithm-x-001", "suite": "algorithm", "split": "test", "dataset_version": "dev-v1",
        "source": "synthetic", "session": {"synthetic_path": "evals/data/sessions/synthetic/syn-001.json"},
        "expected": {"labels": ["two_pointers"]}, "label_source": "human_written", "tags": [], "notes": ""}


@pytest.fixture
def evals_root(tmp_path):
    root = tmp_path / "evals"
    for split in ("dev", "test"):
        f = root / "data" / "algorithm" / split / "cases.jsonl"
        f.parent.mkdir(parents=True)
        f.write_text(json.dumps(dict(CASE, split=split, case_id=f"algorithm-{split}-001")) + "\n")
    return root


def load(*a, **kw):
    from tutor.evals.cases import load_cases

    return load_cases(*a, **kw)


def locked():
    from tutor.evals.cases import SplitLockedError

    return SplitLockedError


def test_dev_loads_without_ceremony(evals_root):
    assert [c.case_id for c in load("algorithm", "dev", root=evals_root)] == ["algorithm-dev-001"]


def test_test_split_is_refused_without_a_milestone(evals_root):
    with pytest.raises(locked()):
        load("algorithm", "test", root=evals_root)


def test_test_split_is_refused_for_an_unapproved_milestone(evals_root):
    (evals_root / "test_approvals.json").write_text(json.dumps({"approved": ["M3"]}))
    with pytest.raises(locked()):
        load("algorithm", "test", root=evals_root, milestone="M7")


def test_test_split_is_refused_when_no_approvals_file_exists(evals_root):
    with pytest.raises(locked()):
        load("algorithm", "test", root=evals_root, milestone="M7")


def test_test_split_loads_for_an_approved_milestone(evals_root):
    (evals_root / "test_approvals.json").write_text(json.dumps({"approved": ["M7"]}))
    assert len(load("algorithm", "test", root=evals_root, milestone="M7")) == 1


@pytest.mark.parametrize("suite,split", [("../algorithm/test", "dev"), ("algorithm", "../test"),
                                         ("algorithm/../algorithm", "test"), ("algorithm", "TEST")])
def test_the_lock_cannot_be_walked_around(evals_root, suite, split):
    from tutor.evals.cases import SplitLockedError

    with pytest.raises((SplitLockedError, ValueError)):
        load(suite, split, root=evals_root)


# ---------------------------------------------------------------- label fence


def _src_files():
    return [p for p in sorted((REPO / "src" / "tutor").rglob("*.py"))
            if "evals" not in p.relative_to(REPO / "src" / "tutor").parts]


def test_no_inference_module_reaches_eval_labels():
    hits = []
    for f in _src_files():
        text = f.read_text()
        if re.search(r"evals[/\\\\\"' ,]+data|\"evals\"\\s*/\\s*\"data\"", text):
            hits.append(f"{f.relative_to(REPO)}: refers to evals/data")
        for node in ast.walk(ast.parse(text)):
            mod = (node.module or "") if isinstance(node, ast.ImportFrom) else ""
            names = [a.name for a in node.names] if isinstance(node, (ast.Import, ast.ImportFrom)) else []
            if mod.startswith("tutor.evals") or any(n.startswith("tutor.evals") for n in names):
                hits.append(f"{f.relative_to(REPO)}: imports {mod or names}")
    # cli.py is the one allowed caller: it wires the eval runner (tutor-eval) and nothing else.
    hits = [h for h in hits if not h.startswith("src/tutor/cli.py")]
    assert not hits, "inference code must not reach eval data or cases:\n" + "\n".join(hits)
