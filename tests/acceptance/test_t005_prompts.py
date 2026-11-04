"""Acceptance tests for T-005: prompt loader + manifest.

Tester-owned (`/test write T-005`, 2026-11-03). Interfaces, agreed with the human because
architecture §7 doesn't name them all (D-024):

    tutor.prompts.load_prompt(name, version, *, root=None) -> LoadedPrompt   # root defaults to prompts/
    LoadedPrompt: name, version, text (body after the front matter), sha256 (of the file's bytes),
                  variables (declared, in order); .substitute(variables: Mapping[str, str]) -> str
    tutor.prompts.PromptError
    `tutor prompts check [--root DIR]` -> exit 0 if prompts/manifest.json matches, else 1

All prompts here are hand-built in a temp dir; the real prompts/ is checked by
tests/contract/test_prompt_manifest.py.
"""

import hashlib
import json

import pytest

DEMO = """---
name: demo
version: v1
field: demo
variables: [problem_title, final_code]
output_schema: DemoOutput
---
Problem: $problem_title
Code:
$final_code
Costs $$5.
"""
BODY = "Problem: $problem_title\nCode:\n$final_code\nCosts $$5.\n"


def write(root, rel, content):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


@pytest.fixture
def root(tmp_path):
    write(tmp_path, "demo/v1.md", DEMO)
    return tmp_path


def load(*a, **kw):
    from tutor.prompts import load_prompt

    return load_prompt(*a, **kw)


def perr():
    from tutor.prompts import PromptError

    return PromptError


# ---------------------------------------------------------------- load_prompt


def test_load_prompt_returns_text_hash_and_declared_variables(root):
    p = load("demo", "v1", root=root)
    assert (p.name, p.version) == ("demo", "v1")
    assert p.text == BODY
    assert p.sha256 == hashlib.sha256((root / "demo" / "v1.md").read_bytes()).hexdigest()
    assert list(p.variables) == ["problem_title", "final_code"]


def test_substitute_fills_every_variable(root):
    out = load("demo", "v1", root=root).substitute({"problem_title": "Two Sum", "final_code": "return []"})
    assert out == "Problem: Two Sum\nCode:\nreturn []\nCosts $5.\n"


def test_substitute_raises_on_a_missing_variable(root):
    with pytest.raises(perr(), match="final_code"):
        load("demo", "v1", root=root).substitute({"problem_title": "Two Sum"})


def test_substitute_raises_on_an_extra_variable(root):
    with pytest.raises(perr(), match="verdict"):
        load("demo", "v1", root=root).substitute({"problem_title": "x", "final_code": "y", "verdict": "Accepted"})


def test_a_missing_prompt_file_raises(root):
    with pytest.raises(perr()):
        load("demo", "v2", root=root)
    with pytest.raises(perr()):
        load("nothing", "v1", root=root)


@pytest.mark.parametrize("change,why", [
    (("name: demo", "name: other"), "front matter name differs from the path"),
    (("version: v1", "version: v2"), "front matter version differs from the path"),
    (("$final_code\n", "$final_code $secret\n"), "body uses a variable that isn't declared"),
    (("[problem_title, final_code]", "[problem_title, final_code, unused]"), "declared variable never used"),
])
def test_front_matter_must_agree_with_path_and_body(tmp_path, change, why):
    write(tmp_path, "demo/v1.md", DEMO.replace(*change))
    with pytest.raises(perr()):
        load("demo", "v1", root=tmp_path)


def test_a_file_without_front_matter_raises(tmp_path):
    write(tmp_path, "demo/v1.md", BODY)
    with pytest.raises(perr()):
        load("demo", "v1", root=tmp_path)


def test_default_root_is_the_repo_prompts_dir():
    from tutor.config import REPO_ROOT

    with pytest.raises(perr()) as err:
        load("no-such-prompt-anywhere", "v1")
    assert str(REPO_ROOT / "prompts" / "no-such-prompt-anywhere" / "v1.md") in str(err.value), \
        "the error names the file it looked for"


# ---------------------------------------------------------------- tutor prompts check


def check(root) -> int:
    from tutor.cli import main

    return main(["prompts", "check", "--root", str(root)])


def manifest(root, entries):
    (root / "manifest.json").write_text(json.dumps(entries, indent=2))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_check_passes_when_every_file_matches(root, capsys):
    j = write(root, "judges/timeline/v1.md", DEMO.replace("name: demo", "name: timeline"))
    manifest(root, {"demo/v1.md": sha(root / "demo" / "v1.md"), "judges/timeline/v1.md": sha(j)})
    assert check(root) == 0


def test_check_fails_when_a_released_file_was_edited(root):
    manifest(root, {"demo/v1.md": sha(root / "demo" / "v1.md")})
    (root / "demo" / "v1.md").write_text(DEMO.replace("Costs", "Now costs"))
    assert check(root) == 1


def test_check_names_the_edited_file(root, capsys):
    manifest(root, {"demo/v1.md": sha(root / "demo" / "v1.md")})
    (root / "demo" / "v1.md").write_text(DEMO + "\n")
    rc = check(root)
    out = capsys.readouterr()
    assert rc == 1 and "demo/v1.md" in out.out + out.err


def test_check_fails_on_a_file_with_no_manifest_entry(root, capsys):
    write(root, "demo/v2.md", DEMO.replace("version: v1", "version: v2"))
    manifest(root, {"demo/v1.md": sha(root / "demo" / "v1.md")})
    rc = check(root)
    out = capsys.readouterr()
    assert rc == 1 and "demo/v2.md" in out.out + out.err


def test_check_fails_on_an_entry_whose_file_is_gone(root, capsys):
    manifest(root, {"demo/v1.md": sha(root / "demo" / "v1.md"), "demo/v0.md": "0" * 64})
    rc = check(root)
    out = capsys.readouterr()
    assert rc == 1 and "demo/v0.md" in out.out + out.err


def test_check_fails_without_a_manifest(root):
    assert check(root) == 1
