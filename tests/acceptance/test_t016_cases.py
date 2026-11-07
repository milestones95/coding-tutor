"""Acceptance tests for T-016: eval cases load into `Case`, and each case's `Session` comes from the
right place (architecture §8.1; D-016, D-048, D-049). Tester-owned (2026-11-07).

    tutor.evals.cases: Case, load_cases(suite, split, *, root=None, milestone=None) -> list[Case],
                       load_case_session(case, *, settings, root=None) -> Session,
                       SplitLockedError, CaseError
    `root` is the evals directory (default <repo>/evals); a synthetic_path is relative to its parent.
"""

import json
import shutil
from pathlib import Path

import pytest

from _capture_fixture import build

REPO = Path(__file__).resolve().parents[2]
SYN = REPO / "evals" / "data" / "sessions" / "synthetic"


def _case(**kw):
    base = {"case_id": "algorithm-dev-001", "suite": "algorithm", "split": "dev", "dataset_version": "dev-v1",
            "source": "synthetic", "session": {"synthetic_path": "evals/data/sessions/synthetic/syn-001.json"},
            "expected": {"labels": ["two_pointers"]}, "label_source": "human_written", "tags": [], "notes": ""}
    return {**base, **kw}


@pytest.fixture
def repo(tmp_path):
    """A small repo: evals/data/algorithm/dev/cases.jsonl plus one synthetic session copied in."""
    syn = tmp_path / "evals" / "data" / "sessions" / "synthetic"
    syn.mkdir(parents=True)
    for name in ("syn-001.json", "syn-001.meta.json"):
        shutil.copy(SYN / name, syn / name)
    return tmp_path


def write_cases(repo, rows, suite="algorithm", split="dev"):
    f = repo / "evals" / "data" / suite / split / "cases.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(json.dumps(r) + "\n" for r in rows))


def cases():
    import tutor.evals.cases as m

    return m


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs"),
                              "TUTOR__PATHS__VERDICTS": str(tmp_path / "none.csv")}, dotenv_path=tmp_path / "none.env")


def test_dw1_cases_load_with_every_field(repo):
    write_cases(repo, [_case(), _case(case_id="algorithm-dev-002", tags=["near_miss"])])
    loaded = cases().load_cases("algorithm", "dev", root=repo / "evals")
    assert [c.case_id for c in loaded] == ["algorithm-dev-001", "algorithm-dev-002"]
    c = loaded[0]
    assert (c.suite, c.split, c.dataset_version, c.source, c.label_source) == (
        "algorithm", "dev", "dev-v1", "synthetic", "human_written")
    assert c.expected == {"labels": ["two_pointers"]}


@pytest.mark.parametrize("bad", [
    {"source": "made_up"}, {"split": "train"}, {"suite": "algorithm", "split": "test"},
    {"session": {}}, {"session": {"capture_session_id": "x", "synthetic_path": "y"}},
    {"label_source": "model"}, {"unknown_field": 1},
])
def test_dw1_a_malformed_case_is_rejected(repo, bad):
    write_cases(repo, [_case(**bad)])
    with pytest.raises(cases().CaseError):
        cases().load_cases("algorithm", "dev", root=repo / "evals")


def test_dw1_case_ids_are_unique(repo):
    write_cases(repo, [_case(), _case()])
    with pytest.raises(cases().CaseError):
        cases().load_cases("algorithm", "dev", root=repo / "evals")


def test_dw1_a_synthetic_case_loads_its_session(repo, settings):
    write_cases(repo, [_case()])
    [c] = cases().load_cases("algorithm", "dev", root=repo / "evals")
    s = cases().load_case_session(c, settings=settings, root=repo / "evals")
    assert s.session_id == "syn-001" and s.problem.slug == "container-with-most-water"


@pytest.mark.parametrize("verdict", ["rejected", None])
def test_dw1_an_unaccepted_synthetic_session_is_refused(repo, settings, verdict):
    meta = repo / "evals" / "data" / "sessions" / "synthetic" / "syn-001.meta.json"
    if verdict is None:
        meta.unlink()
    else:
        meta.write_text(json.dumps(dict(json.loads(meta.read_text()), verdict=verdict)))
    write_cases(repo, [_case()])
    [c] = cases().load_cases("algorithm", "dev", root=repo / "evals")
    with pytest.raises(cases().CaseError):
        cases().load_case_session(c, settings=settings, root=repo / "evals")


def test_dw1_a_synthetic_path_outside_the_synthetic_folder_is_refused(repo, settings):
    write_cases(repo, [_case(session={"synthetic_path": "evals/data/sessions/synthetic/../../../../etc/passwd"})])
    [c] = cases().load_cases("algorithm", "dev", root=repo / "evals")
    with pytest.raises(cases().CaseError):
        cases().load_case_session(c, settings=settings, root=repo / "evals")


def test_dw1_a_real_case_loads_from_the_frozen_copy(repo, tmp_path):
    from tutor.config import load_settings

    frozen = build(tmp_path / "frozen.db", sessions=[{"id": "real-1", "started_at": "2026-11-01T10:00:00.000Z"}],
                   snapshots=[{"session_id": "real-1", "ts": f"2026-11-01T10:0{i}:00.000Z", "code": f"x = {i}"}
                              for i in range(3)])
    before = frozen.read_bytes()
    s = load_settings(env={"TUTOR__PATHS__EVAL_CAPTURE_DB": str(frozen),
                           "TUTOR__PATHS__CAPTURE_DB": str(tmp_path / "live-not-used.db"),
                           "TUTOR__PATHS__VERDICTS": str(tmp_path / "none.csv"),
                           "TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")
    write_cases(repo, [_case(source="real", session={"capture_session_id": "real-1"})])
    [c] = cases().load_cases("algorithm", "dev", root=repo / "evals")
    sess = cases().load_case_session(c, settings=s, root=repo / "evals")
    assert sess.session_id == "real-1"
    assert frozen.read_bytes() == before
    assert not (tmp_path / "live-not-used.db").exists(), "real cases read the frozen copy, never the live DB"


def test_dw1_a_missing_cases_file_is_a_case_error(repo):
    with pytest.raises(cases().CaseError):
        cases().load_cases("algorithm", "dev", root=repo / "evals")
