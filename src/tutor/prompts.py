"""Versioned prompt files and their manifest (architecture §7, rule 6, D-024).

A prompt is `prompts/<name>/v<N>.md`: front matter, then a `string.Template` body (`$name`,
`$$` for a literal dollar). Templates have no logic, so what a model receives is exactly the
file plus the variables, which is what makes a prompt version mean something in an eval record.

The loader checks the file agrees with itself: the front matter's name and version match the
path, and the declared `variables` are exactly the placeholders the body uses. A mismatch is a
`PromptError` at load time, long before a half-filled prompt could reach a model.

`prompts/manifest.json` maps each file (relative to `prompts/`) to the sha256 of its bytes. A
released version is immutable; `check_manifest` reports any file that was edited, is
unlisted, or is listed but gone.
"""

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from string import Template

from tutor.config import REPO_ROOT

PROMPTS_ROOT = REPO_ROOT / "prompts"
MANIFEST_NAME = "manifest.json"
_VERSION = re.compile(r"v\d+")
_KEY_VALUE = re.compile(r"([a-z_][a-z0-9_]*):\s*(.*)")
_LIST = re.compile(r"\[(.*)\]")


class PromptError(Exception):
    """A prompt file that can't be loaded or filled. The message names the file or variables."""


@dataclass(frozen=True)
class LoadedPrompt:
    name: str
    version: str
    text: str  # the template body, after the front matter
    sha256: str  # of the whole file's bytes, as recorded in the manifest
    variables: tuple[str, ...]  # declared in the front matter, in order

    def substitute(self, variables: Mapping[str, str]) -> str:
        """Fill the template. Every declared variable must be given, and nothing else."""
        missing = [v for v in self.variables if v not in variables]
        extra = sorted(set(variables) - set(self.variables))
        if missing or extra:
            parts = ([f"missing {missing}"] if missing else []) + ([f"unexpected {extra}"] if extra else [])
            raise PromptError(f"{self.name}/{self.version}: {'; '.join(parts)}")
        return Template(self.text).substitute(variables)


def parse_front_matter(raw: str, where: str) -> tuple[dict[str, str | list[str]], str]:
    """Split `---` front matter from the body.

    Only the flat form §7 shows is accepted: `key: value` lines, and `key: [a, b]` lists. That
    is all a prompt needs; anything richer is rejected rather than half-parsed (no YAML
    dependency for six lines).
    """
    lines = raw.split("\n")
    if not lines or lines[0].strip() != "---":
        raise PromptError(f"{where}: no front matter (the file must start with a '---' line)")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise PromptError(f"{where}: front matter is not closed with '---'") from None
    meta: dict[str, str | list[str]] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        m = _KEY_VALUE.fullmatch(line.strip())
        if not m:
            raise PromptError(f"{where}: front matter line is not 'key: value': {line!r}")
        key, value = m.groups()
        if key in meta:
            raise PromptError(f"{where}: front matter key {key!r} appears twice")
        lst = _LIST.fullmatch(value.strip())
        meta[key] = [x.strip() for x in lst.group(1).split(",") if x.strip()] if lst else value.strip()
    return meta, "\n".join(lines[end + 1:])


def load_prompt(name: str, version: str, *, root: Path | None = None) -> LoadedPrompt:
    """Load `<root>/<name>/<version>.md` (root defaults to the repo's `prompts/`)."""
    if not _VERSION.fullmatch(version):
        raise PromptError(f"{name}: version must look like 'v1', not {version!r}")
    path = (root or PROMPTS_ROOT) / name / f"{version}.md"
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise PromptError(f"prompt file not found: {path}") from None
    where = f"{name}/{version}.md"
    meta, body = parse_front_matter(data.decode("utf-8"), where)

    for key, expected in (("name", name), ("version", version)):
        if meta.get(key) != expected:
            raise PromptError(f"{where}: front matter {key} is {meta.get(key)!r}, the path says {expected!r}")
    declared = meta.get("variables")
    if not isinstance(declared, list):
        raise PromptError(f"{where}: front matter needs 'variables: [..]'")

    template = Template(body)
    if not template.is_valid():
        raise PromptError(f"{where}: body has a '$' that is not a placeholder (write '$$' for a literal $)")
    used = template.get_identifiers()
    undeclared = sorted(set(used) - set(declared))
    unused = [v for v in declared if v not in used]
    if undeclared or unused:
        parts = ([f"used but not declared {undeclared}"] if undeclared else []) + \
                ([f"declared but never used {unused}"] if unused else [])
        raise PromptError(f"{where}: {'; '.join(parts)}")

    return LoadedPrompt(name=name, version=version, text=body,
                        sha256=hashlib.sha256(data).hexdigest(), variables=tuple(declared))


def prompt_files(root: Path) -> dict[str, Path]:
    """Every prompt file under `root`, keyed as the manifest keys it: `<name>/v<N>.md`."""
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*.md"))}


def check_manifest(root: Path | None = None) -> list[str]:
    """Problems with `<root>/manifest.json`, one line each; empty means every file matches."""
    root = root or PROMPTS_ROOT
    manifest_path = root / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text())
    except FileNotFoundError:
        return [f"{manifest_path}: missing"]
    except json.JSONDecodeError as e:
        return [f"{manifest_path}: not valid JSON ({e})"]
    if not isinstance(manifest, dict):
        return [f"{manifest_path}: must be a JSON object of '<name>/v<N>.md': sha256"]

    files = prompt_files(root)
    problems = []
    for key, path in files.items():
        if key not in manifest:
            problems.append(f"{key}: not in the manifest")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != manifest[key]:
            problems.append(f"{key}: content no longer matches its recorded sha256 (released prompts are "
                            "immutable; make a new version)")
    problems += [f"{key}: in the manifest but the file is gone" for key in sorted(manifest.keys() - files.keys())]
    return problems
