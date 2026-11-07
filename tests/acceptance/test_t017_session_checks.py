"""Acceptance tests for T-017: the synthetic-session checks grade correctly (architecture §8.5;
D-043, D-048). Tester-owned (2026-11-07).

Each rule is graded on a hand-made session: a valid one passes, and a copy broken in exactly
one way is caught for that reason. The last test runs the checks over the 20 committed sessions
(with their recorded waivers).
"""

import copy
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("checks", REPO / "evals" / "generate" / "checks.py")
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)

FINAL = "class Solution:\n    def f(self, nums):\n        return sum(nums)\n"
SPEC = {"id": "syn-900", "problem": {"slug": "x", "title": "X", "difficulty": "Easy", "tags": ["array"]},
        "duration_min": 10, "runs": 2, "verdict": {"status": "Wrong Answer", "tests_passed": 3, "tests_total": 9},
        "labels": {"failure_type": "edge_case_missed", "algorithms": ["dynamic_programming"]},
        "story": {"on_track_algorithms": None}, "key_facts": ["the final submit fails at 3/9 on an empty list"]}


def _valid():
    return {"session_id": "syn-900",
            "problem": {**SPEC["problem"], "description": None},
            "snapshots": [{"ts": "2026-10-20T15:00:00.000Z", "code": "class Solution:\n    pass\n", "language": "python3"},
                          {"ts": "2026-10-20T15:04:00.000Z", "code": "class Solution:\n    def f(self, nums):\n        return 0\n",
                           "language": "python3"},
                          {"ts": "2026-10-20T15:09:00.000Z", "code": FINAL, "language": "python3"}],
            "events": [{"kind": "run", "ts": "2026-10-20T15:05:00.000Z", "status": "Wrong Answer (sample tests)",
                        "tests_passed": 0, "tests_total": 2, "error_detail": "Output: 0\nExpected: 6"},
                       {"kind": "run", "ts": "2026-10-20T15:09:30.000Z", "status": "Passed sample tests",
                        "tests_passed": 2, "tests_total": 2, "error_detail": None},
                       {"kind": "submit", "ts": "2026-10-20T15:10:00.000Z", "verdict": "Wrong Answer",
                        "tests_passed": 3, "tests_total": 9, "error_detail": "Input: []\nOutput: 0\nExpected: -1",
                        "source": "capture_submit"}],
            "submit_capture_reliable": True}


def run(raw, spec=SPEC, final=FINAL, waivers=frozenset()):
    return checks.check_session(raw, spec, final, set(waivers))


def broken(change):
    raw = copy.deepcopy(_valid())
    change(raw)
    return raw


def test_a_valid_session_passes():
    assert run(_valid()) == ([], [])


@pytest.mark.parametrize("rule,change", [
    ("schema", lambda r: r["snapshots"][0].update(ts="2026-10-20T15:00:00")),          # no timezone
    ("problem", lambda r: r["problem"].update(tags=["array", "sorting"])),
    ("reliable", lambda r: r.update(submit_capture_reliable=False)),
    ("order", lambda r: r["snapshots"].reverse()),
    ("spacing", lambda r: r["snapshots"][1].update(ts="2026-10-20T15:00:03.000Z")),
    ("repeat", lambda r: r["snapshots"][1].update(code=r["snapshots"][0]["code"])),
    ("language", lambda r: r["snapshots"][0].update(language="java")),
    ("duration", lambda r: [e.update(ts="2026-10-20T15:20:00.000Z") for e in r["events"] if e["kind"] == "submit"]),
    ("runs", lambda r: r["events"].__setitem__(slice(0, 2), [])),
    ("run_status", lambda r: r["events"][0].update(status="Wrong answer")),
    ("final_code", lambda r: r["snapshots"][-1].update(code=FINAL + "\n")),
    ("submit", lambda r: r["events"][-1].update(tests_passed=4)),
    ("submit", lambda r: r["events"].append(dict(r["events"][-1], ts="2026-10-20T15:10:30.000Z"))),
    ("leak", lambda r: r["snapshots"][1].update(code="class Solution:\n    pass  # use dynamic programming here\n")),
    ("leak", lambda r: r["snapshots"][1].update(code="class Solution:\n    pass  # this has a bug\n")),
    ("leak", lambda r: r["events"][0].update(error_detail="the final submit fails at 3/9 on an empty list")),
])
def test_each_rule_catches_its_break(rule, change):
    problems, _ = run(broken(change))
    assert any(p.startswith(rule + ":") or p.startswith(rule) for p in problems), (rule, problems)


def test_never_submitted_sessions_must_have_no_submit():
    spec = dict(SPEC, verdict=None, labels={"failure_type": "did_not_finish", "algorithms": ["greedy"]})
    problems, _ = run(_valid(), spec=spec)
    assert any(p.startswith("submit:") for p in problems)
    raw = broken(lambda r: r["events"].pop())
    raw["events"][-1]["ts"] = "2026-10-20T15:09:30.000Z"
    assert not [p for p in run(raw, spec=spec)[0] if p.startswith("submit:")]


def test_identifiers_and_leetcode_boilerplate_are_not_leaks():
    code = ("# Definition for singly-linked list.\n# class ListNode:\n#     def __init__(self, val=0, next=None):\n"
            "#         self.val = val\nclass Solution:\n    def f(self, nums):\n        stack = []  # days still waiting\n"
            "        return 0\n")
    raw = broken(lambda r: r["snapshots"][1].update(code=code))
    assert run(raw, spec=dict(SPEC, labels={"failure_type": "edge_case_missed", "algorithms": ["stack", "linked_list"]}))[0] == []


def test_a_waiver_moves_a_problem_out_of_the_failures():
    raw = broken(lambda r: [e.update(ts="2026-10-20T15:20:00.000Z") for e in r["events"] if e["kind"] == "submit"])
    problems, waived = run(raw, waivers={"duration"})
    assert problems == [] and waived and waived[0].startswith("duration:")


def test_the_committed_synthetic_sessions_all_pass():
    assert checks.main([]) == 0
