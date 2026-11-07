"""Contract + acceptance: the eval runner (T-022; architecture §8.2, §8.3; rules 1, 2, 7).
Tester-owned (2026-11-07; interfaces D-051).

    tutor.evals.runner.run(suite, split, *, predictor, settings, repeats=1, milestone=None,
                           root=None, results_dir=None) -> dict   # the result record
    tutor.evals.runner.estimate(suite, split, *, predictor, repeats=1, root=None) -> dict
    tutor.evals.runner.summary_line(record) -> str
    A predictor is a callable Session -> output dict, with `.name` and `.version`.
"""

import json
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SYN = REPO / "evals" / "data" / "sessions" / "synthetic"
RECORD_KEYS = {"run_id", "suite", "split", "dataset_version", "started_at", "finished_at", "git_sha", "git_dirty",
               "provider", "model", "prompt_versions", "prompt_sha256", "condenser_version", "judge", "repeats",
               "cases", "aggregates", "cost_usd_total"}


def _case(n, sid, labels, split="dev"):
    return {"case_id": f"algorithm-{split}-{n:03d}", "suite": "algorithm", "split": split,
            "dataset_version": f"{split}-v1", "source": "synthetic",
            "session": {"synthetic_path": f"evals/data/sessions/synthetic/{sid}.json"},
            "expected": {"labels": labels}, "label_source": "human_written", "tags": [], "notes": ""}


@pytest.fixture
def root(tmp_path):
    syn = tmp_path / "evals" / "data" / "sessions" / "synthetic"
    syn.mkdir(parents=True)
    for sid in ("syn-001", "syn-005", "syn-022"):
        for ext in (".json", ".meta.json"):
            shutil.copy(SYN / f"{sid}{ext}", syn / f"{sid}{ext}")
    for split in ("dev", "test"):
        f = tmp_path / "evals" / "data" / "algorithm" / split / "cases.jsonl"
        f.parent.mkdir(parents=True)
        rows = [_case(1, "syn-001", ["two_pointers"], split), _case(2, "syn-005", ["stack"], split),
                _case(3, "syn-022", ["union_find"], split)]
        f.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return tmp_path / "evals"


@pytest.fixture
def settings(tmp_path):
    from tutor.config import load_settings

    return load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")


class Fixed:
    """Predicts by problem slug; records what it was handed."""
    name, version = "fixed", "t-1"

    def __init__(self, answers, fail_on=()):
        self.answers, self.fail_on, self.seen = answers, set(fail_on), []

    def __call__(self, session):
        self.seen.append(session)
        if session.problem.slug in self.fail_on:
            raise RuntimeError("predictor failed")
        return {"labels": self.answers.get(session.problem.slug, [])}


ANSWERS = {"container-with-most-water": ["two_pointers"], "daily-temperatures": ["hash_map"],
           "longest-consecutive-sequence": ["union_find", "hash_map"]}


def runner():
    import tutor.evals.runner as r

    return r


def test_the_runner_refuses_the_test_split_without_an_approved_milestone(root, settings):
    from tutor.evals.cases import SplitLockedError

    with pytest.raises(SplitLockedError):
        runner().run("algorithm", "test", predictor=Fixed(ANSWERS), settings=settings, root=root)
    assert not (root / "results").exists(), "nothing is written for a refused run"


def test_the_record_has_every_section_8_3_field(root, settings):
    rec = runner().run("algorithm", "dev", predictor=Fixed(ANSWERS), settings=settings, root=root)
    assert RECORD_KEYS <= rec.keys()
    assert (rec["suite"], rec["split"], rec["dataset_version"], rec["condenser_version"]) == ("algorithm", "dev", "dev-v1", "c1")
    assert rec["model"] == "fixed@t-1" and rec["repeats"] == 1
    assert len(rec["cases"]) == 3 and {"case_id", "repeat", "output", "grades", "error"} <= rec["cases"][0].keys()
    saved = json.loads((root / "results" / "algorithm" / f"{rec['run_id']}.json").read_text())
    assert saved == rec
    [line] = [json.loads(x) for x in (root / "results" / "index.jsonl").read_text().splitlines()]
    assert line["run_id"] == rec["run_id"] and "cases" not in line


def test_field_functions_receive_a_session_and_nothing_else(root, settings):
    from tutor.models import Session

    p = Fixed(ANSWERS)
    runner().run("algorithm", "dev", predictor=p, settings=settings, root=root)
    assert p.seen and all(type(s) is Session for s in p.seen), "the runner hands predictors a Session only (§4.3 #1)"


def test_accuracy_is_overall_real_and_synthetic_with_counts(root, settings):
    rec = runner().run("algorithm", "dev", predictor=Fixed(ANSWERS), settings=settings, root=root)
    agg = rec["aggregates"]
    assert agg["accuracy"] == pytest.approx(2 / 3)                  # daily-temperatures misses
    assert agg["by_source"]["synthetic"] == {"accuracy": pytest.approx(2 / 3), "n": 3}
    assert agg["by_source"]["real"]["n"] == 0
    assert agg["errors"] == 0


def test_a_predictor_error_counts_as_wrong_and_separately(root, settings):
    rec = runner().run("algorithm", "dev", predictor=Fixed(ANSWERS, fail_on={"container-with-most-water"}),
                       settings=settings, root=root)
    assert rec["aggregates"]["errors"] == 1
    assert rec["aggregates"]["accuracy"] == pytest.approx(1 / 3)
    errored = [c for c in rec["cases"] if c["error"]]
    assert len(errored) == 1 and "predictor failed" in errored[0]["error"]


def test_repeats_and_consistency(root, settings):
    rec = runner().run("algorithm", "dev", predictor=Fixed(ANSWERS), settings=settings, root=root, repeats=3)
    assert len(rec["cases"]) == 9 and rec["aggregates"]["consistency"] == 1.0


def test_the_summary_line_names_every_version(root, settings):
    line = runner().summary_line(runner().run("algorithm", "dev", predictor=Fixed(ANSWERS), settings=settings, root=root))
    for part in ("algorithm_overlap", "0.67", "fixed@t-1", "dev-v1", "c1", "synthetic 0.67 (n=3)"):
        assert part in line, (part, line)


def test_estimate_counts_calls_and_makes_none(root):
    p = Fixed(ANSWERS)
    est = runner().estimate("algorithm", "dev", predictor=p, repeats=2, root=root)
    assert (est["cases"], est["calls"], est["cost_usd"]) == (3, 6, 0.0)
    assert p.seen == []


def test_an_approved_test_run_writes_aggregates_only(root, settings):
    (root / "test_approvals.json").write_text(json.dumps({"approved": ["M7"]}))
    rec = runner().run("algorithm", "test", predictor=Fixed(ANSWERS), settings=settings, root=root, milestone="M7")
    saved = json.loads((root / "results" / "algorithm" / f"{rec['run_id']}.json").read_text())
    assert saved["cases"] == [] and saved["aggregates"]["accuracy"] == pytest.approx(2 / 3)
