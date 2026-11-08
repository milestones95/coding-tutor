"""Grade the grader: `at_most_5_sentences` (T-031; eval plan "5 sentences or fewer"). Tester-owned
(`/test write T-031`, 2026-11-08). Hand-made summaries whose right count is known."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.mark.parametrize("text,n", [
    ("", 0),
    ("   ", 0),
    ("One sentence with no full stop", 1),
    ("You ran it at 16.6 min. It passed 59/90 tests.", 2),
    ("It used e.g. a stack and checked nums[i]. Then it was accepted!", 2),
    ("Did it work? No. It timed out at 41/63. You stopped.", 4),
    ('The error said "IndexError". "Fixed," you wrote. 3 runs followed.', 3),
    ("A. B. C. D. E. F.", 6),
])
def test_count_sentences(text, n):
    from evals.graders.sentence_count import count_sentences

    assert count_sentences(text) == n


@pytest.mark.parametrize("output,value", [
    ({"summary": "One. Two. Three. Four. Five."}, 1.0),
    ({"summary": "One. Two. Three. Four. Five. Six."}, 0.0),
    ({"summary": "Only one."}, 1.0),
    ({"summary": ""}, 0.0),
    ({}, 0.0),
    (None, 0.0),
])
def test_at_most_five_sentences(output, value):
    from evals.graders.sentence_count import SentenceCount

    [g] = SentenceCount().grade(SimpleNamespace(expected={}), output, None)
    assert g.metric == "at_most_5_sentences" and g.value == value
