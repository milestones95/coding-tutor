"""Acceptance tests for T-036: timeline prompt v2 defines "on the right track". Tester-owned
(`/test write T-036`, 2026-11-08). Done-when 1 and the prompt half of 2 are checked here; the eval
half (v2 vs v1 under the calibrated timeline judge, no other item outside its band) is checked at
`/test run` from the result records, because evals don't run in `tests/`.

The human's definition (D-063): a first approach is on the right track if it only needs bug fixes
to pass; it is off track if passing needs a pivot to a different algorithm, and too slow for the
problem's limits counts as not passing.
"""

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
V1, V2 = REPO / "prompts/timeline/v1.md", REPO / "prompts/timeline/v2.md"
DATA = REPO / "evals/data"


def _text():
    return V2.read_text().lower()


def test_v2_exists_pinned_and_in_the_manifest():
    from tutor.config import load_settings
    from tutor.prompts import load_prompt

    assert load_settings().prompts.get("timeline") == "v2", "tutor.toml pins timeline v2"
    p = load_prompt("timeline", "v2")
    assert json.loads((REPO / "prompts/manifest.json").read_text()).get("timeline/v2.md") == p.sha256


def test_v1_is_unchanged():
    want = json.loads((REPO / "prompts/manifest.json").read_text())["timeline/v1.md"]
    from tutor.prompts import load_prompt

    assert load_prompt("timeline", "v1").sha256 == want


def test_v2_reads_the_same_inputs_and_answers_the_same_shape():
    """Only the instructions change: same variables (the one condenser's timeline, rule 3), same output."""
    from tutor.prompts import load_prompt

    v1, v2 = load_prompt("timeline", "v1"), load_prompt("timeline", "v2")
    assert tuple(v2.variables) == tuple(v1.variables)
    assert '{"summary"' in V2.read_text()


def test_v2_defines_on_track_as_only_bug_fixes_needed():
    t = _text()
    assert "on the right track" in t or "on track" in t
    assert "bug" in t, "on track = the idea only needs bug fixes"


def test_v2_says_a_pivot_to_a_different_algorithm_means_off_track():
    t = _text()
    assert "different algorithm" in t or "different approach" in t
    assert "off track" in t or "not on the right track" in t


def test_v2_says_too_slow_for_the_limits_is_off_track():
    t = _text()
    assert ("too slow" in t or "time limit" in t) and ("limit" in t or "constraint" in t)


def test_v2_still_asks_for_the_rest_of_the_checklist():
    t = _text()
    assert "3" in t and "5" in t and "sentence" in t
    assert "approach" in t and "outcome" in t
    assert "do not describe a change of approach" in t or "never changed" in t, "no invented correction"


def test_v2_names_no_dataset_problem():
    """Rule 9: a general rule, never a patch naming a dataset example."""
    t = _text()
    names = set()
    for line in (DATA / "sessions/synthetic/specs.jsonl").read_text().splitlines():
        if line.strip():
            prob = json.loads(line)["problem"]
            names |= {prob["slug"].lower(), prob["title"].lower()}
    for line in (DATA / "sessions/real/labels.jsonl").read_text().splitlines():
        if line.strip():
            slug = json.loads(line)["slug"].lower()
            names |= {slug, slug.replace("-", " ")}
    assert not [n for n in names if n in t], "a dataset problem is named in the prompt"


def test_judge_and_labels_are_untouched_by_this_task():
    """T-036 changes the field prompt only. The judge and its calibration stay as calibrated (D-064, D-067)."""
    manifest = json.loads((REPO / "prompts/manifest.json").read_text())
    judge = REPO / "prompts/judges/timeline/v1.md"
    assert hashlib.sha256(judge.read_bytes()).hexdigest() == manifest["judges/timeline/v1.md"]
    data = json.loads((DATA / "manifest.json").read_text())
    for p in ("evals/data/calibration/timeline/v1.jsonl", "evals/data/timeline/dev/cases.jsonl"):
        assert hashlib.sha256((REPO / p).read_bytes()).hexdigest() == data[p]
