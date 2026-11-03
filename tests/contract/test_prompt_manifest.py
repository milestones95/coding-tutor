"""Prompt manifest — rule 6, architecture §7. Tester-owned; kept for the life of the project
(`/test write T-005`, 2026-11-03).

A released prompt version is immutable. `prompts/manifest.json` maps every prompt file
(`"<name>/v<N>.md"`, relative to `prompts/`, judges and generators included) to the sha256 of
its bytes. Editing a released file breaks its hash; the fix is a new `v<N+1>.md`, never a new
hash for the old file.
"""

import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROMPTS = REPO / "prompts"
MANIFEST = PROMPTS / "manifest.json"


def _manifest() -> dict[str, str]:
    assert MANIFEST.is_file(), "prompts/manifest.json is missing"
    data = json.loads(MANIFEST.read_text())
    assert isinstance(data, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in data.items())
    return data


def _files() -> dict[str, Path]:
    return {p.relative_to(PROMPTS).as_posix(): p for p in sorted(PROMPTS.rglob("*.md"))}


def test_every_prompt_file_is_in_the_manifest_and_every_entry_has_a_file():
    m, files = _manifest(), _files()
    assert not files.keys() - m.keys(), f"prompt files with no manifest entry: {sorted(files.keys() - m.keys())}"
    assert not m.keys() - files.keys(), f"manifest entries with no file: {sorted(m.keys() - files.keys())}"


def test_every_prompt_file_matches_its_recorded_hash():
    m = _manifest()
    changed = [k for k, p in _files().items() if k in m and hashlib.sha256(p.read_bytes()).hexdigest() != m[k]]
    assert not changed, f"released prompt edited in place (make a new version instead): {changed}"


def test_prompt_files_follow_the_naming_convention():
    bad = [k for k in _files() if not re.fullmatch(r"([a-z0-9_]+/)+v\d+\.md", k)]
    assert not bad, f"prompt files must be prompts/<name>/v<N>.md: {bad}"
