"""Acceptance tests for T-030: the timeline suite (architecture §8.1; D-059). Tester-owned
(`/test write T-030`, 2026-11-08).

    evals/data/timeline/{dev,test}/cases.jsonl — one case per session, each session in the split it
    has in dev-v1 (the failure suite holds every session, so it is the reference).
    expected = {checklist: {approaches[], course_correction, final_approach, outcome}, key_facts[]}
    outcome comes from the verdict, never a label: "<verdict>, p/t tests passed" or "not submitted".

Test-split cases are read here only to check shape and membership; nothing about them is printed.
"""

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "evals" / "data"
SPECS = DATA / "sessions" / "synthetic" / "specs.jsonl"
REAL = DATA / "sessions" / "real" / "labels.jsonl"


def _cases(suite, split):
    return [json.loads(line) for line in (DATA / suite / split / "cases.jsonl").read_text().splitlines() if line.strip()]


def _ref(case):
    return json.dumps(case["session"], sort_keys=True)


def _story():
    """session ref → (story, key_facts, verdict-or-None) from the human's label sources."""
    out = {}
    for line in SPECS.read_text().splitlines():
        s = json.loads(line)
        ref = json.dumps({"synthetic_path": f"evals/data/sessions/synthetic/{s['id']}.json"}, sort_keys=True)
        out[ref] = (s["story"], s["key_facts"], s["verdict"])
    for line in REAL.read_text().splitlines():
        r = json.loads(line)
        out[json.dumps({"capture_session_id": r["capture_session_id"]}, sort_keys=True)] = (r["story"], r["key_facts"], "real")
    return out


@pytest.mark.parametrize("split", ["dev", "test"])
def test_one_case_per_session_in_the_same_split_as_dev_v1(split):
    timeline = [_ref(c) for c in _cases("timeline", split)]
    assert len(timeline) == len(set(timeline)), "a session appears twice"
    assert set(timeline) == {_ref(c) for c in _cases("failure", split)}, f"timeline/{split} sessions differ from dev-v1's"


@pytest.mark.parametrize("split", ["dev", "test"])
def test_cases_load_with_the_runner_contract(split):
    from tutor.evals.cases import Case

    for c in _cases("timeline", split):
        case = Case.model_validate(c)
        want = "dev-v2" if split == "dev" else "test-v1"   # dev-v2: syn-003 relabel, 2026-11-08 (D-063)
        assert (case.suite, case.split, case.dataset_version) == ("timeline", split, want)
        assert case.label_source == "human_written"


@pytest.mark.parametrize("split", ["dev", "test"])
def test_expected_holds_the_checklist_and_key_facts_from_the_human_labels(split):
    labels = _story()
    bad = 0
    for c in _cases("timeline", split):
        e = c["expected"]
        assert set(e) == {"checklist", "key_facts"}
        assert set(e["checklist"]) == {"approaches", "course_correction", "final_approach", "outcome"}
        story, key_facts, _ = labels[_ref(c)]
        bad += (e["checklist"]["approaches"] != story["approaches"]
                or e["checklist"]["course_correction"] != story["course_correction"]
                or e["checklist"]["final_approach"] != story["final_approach"]
                or e["key_facts"] != key_facts)
    assert bad == 0, f"{bad} {split} case(s) don't match the human's labels"


def test_on_track_algorithms_is_not_in_the_checklist():
    """It answers 'what would have worked', which a summary of what happened never needs (D-039)."""
    for split in ("dev", "test"):
        assert all("on_track_algorithms" not in json.dumps(c["expected"]) for c in _cases("timeline", split))


@pytest.mark.parametrize("split", ["dev", "test"])
def test_outcome_is_read_from_the_verdict(split):
    from tutor.config import load_settings
    from tutor.capture.loader import CaptureLoader
    from tutor.fields.deterministic import status

    labels = _story()
    settings = load_settings()
    loader = CaptureLoader(settings.paths.eval_capture_db, mode="immutable", settings=settings, run_id="t030")
    bad = 0
    for c in _cases("timeline", split):
        _, _, v = labels[_ref(c)]
        if v == "real":
            st = status(loader.load_session(c["session"]["capture_session_id"]), settings=settings, run_id="t030")
            verdict, passed, total = st.leetcode_verdict, st.tests_passed, st.tests_total
        elif v is None:
            verdict = passed = total = None
        else:
            verdict, passed, total = v["status"], v["tests_passed"], v["tests_total"]
        want = "not submitted" if verdict is None else f"{verdict}, {passed}/{total} tests passed"
        bad += c["expected"]["checklist"]["outcome"] != want
    assert bad == 0, f"{bad} {split} case(s) have an outcome that isn't the verdict"


def test_the_timeline_files_are_frozen_by_the_manifest():
    manifest = json.loads((DATA / "manifest.json").read_text())
    assert {"evals/data/timeline/dev/cases.jsonl", "evals/data/timeline/test/cases.jsonl"} <= manifest.keys()
