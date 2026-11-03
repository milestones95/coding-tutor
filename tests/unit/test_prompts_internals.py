"""Builder unit tests for prompts.py internals (T-005)."""

import hashlib
import json

import pytest

from tutor.prompts import PromptError, check_manifest, load_prompt, parse_front_matter


def test_front_matter_lists_and_scalars():
    meta, body = parse_front_matter("---\nname: x\nvariables: [a, b ,c]\nempty: []\n---\nhi $a\n", "x")
    assert meta == {"name": "x", "variables": ["a", "b", "c"], "empty": []}
    assert body == "hi $a\n"


@pytest.mark.parametrize("raw", [
    "---\nname: x\n",                      # never closed
    "---\n- a list item\n---\nbody",       # not key: value
    "---\nname: x\nname: y\n---\nbody",    # duplicate key
])
def test_front_matter_rejects_what_it_cannot_read(raw):
    with pytest.raises(PromptError):
        parse_front_matter(raw, "x")


def test_a_lone_dollar_in_the_body_is_rejected(tmp_path):
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "v1.md").write_text("---\nname: p\nversion: v1\nvariables: []\n---\ncosts $ 5\n")
    with pytest.raises(PromptError, match=r"\$\$"):
        load_prompt("p", "v1", root=tmp_path)


def test_version_must_look_like_vN(tmp_path):
    with pytest.raises(PromptError, match="v1"):
        load_prompt("p", "1", root=tmp_path)


def test_a_prompt_with_no_variables_loads(tmp_path):
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "v1.md").write_text("---\nname: p\nversion: v1\nvariables: []\n---\nplain\n")
    p = load_prompt("p", "v1", root=tmp_path)
    assert p.variables == () and p.substitute({}) == "plain\n"


def test_manifest_problems_are_listed_one_per_file(tmp_path):
    (tmp_path / "a").mkdir()
    a = tmp_path / "a" / "v1.md"
    a.write_text("x")
    (tmp_path / "manifest.json").write_text(json.dumps({"a/v1.md": hashlib.sha256(b"x").hexdigest()}))
    assert check_manifest(tmp_path) == []
    a.write_text("y")
    (tmp_path / "a" / "v2.md").write_text("z")
    problems = check_manifest(tmp_path)
    assert len(problems) == 2 and problems[0].startswith("a/v1.md") and problems[1].startswith("a/v2.md")


def test_manifest_that_is_not_an_object_is_a_problem(tmp_path):
    (tmp_path / "manifest.json").write_text("[]")
    assert len(check_manifest(tmp_path)) == 1
