"""Contract: failure types v2 (D-079, T-046). Tester-owned (`/test write T-046`, 2026-11-17). Kept for the
project's life.

Every human failure label obeys D-079's status rules, `edge_case_missed` is gone from every label source and
case file, and every tester-owned copy of the failure-type list (spec checker, `synthetic-spec` skill, judge
v3) says the same thing. Test cases are only checked here, never printed. The pipeline's own copies (enum,
migration CHECK, failure prompt) are T-047's, checked by its acceptance tests.
"""

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "evals" / "data"
sys.path.insert(0, str(REPO / "evals" / "build"))
sys.path.insert(0, str(REPO / "evals" / "generate"))

from remap_failure_types import FAILURE_TYPES_V2, LLM_TYPES, VERDICT_STATUS, RemapError, remap  # noqa: E402

LABEL_SOURCES = [DATA / "sessions/synthetic/specs.jsonl", DATA / "sessions/real/labels.jsonl"]


def _lines(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def test_the_v2_list_is_exactly_d079s():
    assert FAILURE_TYPES_V2 == {"none", "too_slow", "wrong_approach", "implementation_bug", "did_not_finish", "unknown"}
    assert LLM_TYPES == {"wrong_approach", "implementation_bug"}


@pytest.mark.parametrize("status,old,new", [
    ("passed", "none", "none"),
    ("failed_too_slow", "too_slow", "too_slow"),
    ("not_submitted", "wrong_approach", "did_not_finish"),
    ("not_submitted", "did_not_finish", "did_not_finish"),
    ("unknown", "implementation_bug", "unknown"),
    ("failed_wrong_answer", "edge_case_missed", "implementation_bug"),
    ("failed_runtime_error", "edge_case_missed", "implementation_bug"),
    ("failed_output_limit", "implementation_bug", "implementation_bug"),
    ("failed_wrong_answer", "wrong_approach", "wrong_approach"),
])
def test_remap_follows_the_table(status, old, new):
    assert remap(old, status) == new


@pytest.mark.parametrize("status,old", [
    ("failed_wrong_answer", "did_not_finish"),   # a submitted session can't be "didn't finish"
    ("failed_wrong_answer", "too_slow"),
    ("passed", "implementation_bug"),
    ("failed_too_slow", "wrong_approach"),
    ("failed_runtime_error", "none"),
])
def test_remap_refuses_what_needs_the_humans_judgment(status, old):
    with pytest.raises(RemapError):
        remap(old, status)


def test_no_label_source_or_case_file_says_edge_case_missed():
    files = LABEL_SOURCES + list(DATA.glob("failure/*/cases.jsonl"))
    hits = [str(p.relative_to(REPO)) for p in files if "edge_case_missed" in p.read_text()]
    assert not hits, f"edge_case_missed still in {hits}"


def test_every_spec_label_obeys_the_status_rules():
    for s in _lines(LABEL_SOURCES[0]):
        status = VERDICT_STATUS[s["verdict"]["status"] if s["verdict"] else "not submitted"]
        ft = s["labels"]["failure_type"]
        assert ft in FAILURE_TYPES_V2 and remap(ft, status) == ft, s["id"]


def test_every_failure_case_label_is_a_v2_type_and_rule_cases_match_their_rule():
    for path in DATA.glob("failure/*/cases.jsonl"):
        for c in _lines(path):
            ft = c["expected"]["failure_type"]
            assert ft in FAILURE_TYPES_V2, c["case_id"]
            if "rule_decided" in c["tags"]:
                assert ft in ("none", "too_slow"), c["case_id"]


def test_the_spec_checker_uses_the_same_list():
    import check_specs
    assert check_specs.FAILURE_TYPES == FAILURE_TYPES_V2


def test_the_skill_lists_the_v2_types():
    text = (REPO / ".claude/skills/synthetic-spec/SKILL.md").read_text()
    section = text[text.index("3. **Failure type**"):text.index("4. **Algorithms**")]
    named = set(re.findall(r"`([a-z_]+)`", section))
    assert FAILURE_TYPES_V2 <= named
    assert "edge_case_missed" not in named - {"edge_case_missed"} or "merged" in section


@pytest.mark.parametrize("version", ["v3", "v4"])
def test_the_judge_defines_exactly_the_failure_types_a_failed_session_can_have(version):
    text = (REPO / f"prompts/judges/failure_explanation/{version}.md").read_text()
    block = text[text.index("Failure types:"):text.index("Person's account:")]
    defined = set(re.findall(r"^- ([a-z_]+)[ :]", block, re.M))
    assert defined == FAILURE_TYPES_V2 - {"none", "unknown"}
