"""Grade the graders (T-022; architecture §8.4; eval plan algorithm metric). Tester-owned (2026-11-07).

Hand-made outputs whose right score is known: the "any overlap counts" rule, and the keyword
baseline on short code snippets.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evals.graders.algorithm_overlap import AlgorithmOverlap  # noqa: E402
from evals.graders.base import GradeContext  # noqa: E402
from evals.graders.keyword_baseline import predict  # noqa: E402


def case(labels):
    return SimpleNamespace(expected={"labels": labels})


@pytest.mark.parametrize("predicted,expected,value", [
    (["hash_map"], ["hash_map"], 1.0),
    (["hash_map", "two_pointers"], ["two_pointers"], 1.0),      # any overlap counts
    (["greedy"], ["dynamic_programming"], 0.0),
    ([], ["stack"], 0.0),                                       # predicting nothing is not a hit
    (["stack", "heap"], ["heap", "bfs"], 1.0),
])
def test_overlap_rule(predicted, expected, value):
    [g] = AlgorithmOverlap().grade(case(expected), {"labels": predicted}, GradeContext())
    assert (g.metric, g.value) == ("algorithm_overlap", value)


def test_overlap_missing_output_scores_zero():
    assert AlgorithmOverlap().grade(case(["stack"]), {}, GradeContext())[0].value == 0.0


@pytest.mark.parametrize("code,label", [
    ("import heapq\nheapq.heappush(h, x)", "heap"),
    ("while node.next:\n    node = node.next", "linked_list"),
    ("q = deque([root])\nn = q.popleft()", "bfs"),
    ("lo, hi = 0, len(a)\nmid = (lo + hi) // 2", "binary_search"),
    ("seen = {}\nfor x in nums:\n    seen[x] = 1", "hash_map"),
    ("dp = [0] * n\ndp[i] = dp[i-1] + 1", "dynamic_programming"),
    ("stack = []\nstack.append(x)\nstack.pop()", "stack"),
    ("parent = {x: x}\ndef find(x):\n    return parent[x]", "union_find"),
    ("n &= (n - 1)", "bit_manipulation"),
])
def test_keyword_baseline_finds_obvious_cues(code, label):
    assert label in predict(code)


def test_keyword_baseline_returns_at_most_two_labels_and_nothing_without_cues():
    assert len(predict("heapq dp stack deque .next {}")) <= 2
    assert predict("return 42") == []
