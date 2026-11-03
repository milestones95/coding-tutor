"""Capture fence — architecture §4.3 #5, D-015. Tester-owned; kept for the life of the project.

Rule 5 says every LLM call goes through one wrapper in `src/tutor/llm/`. Capture lives in
this repo as Node code, so these tests make sure it can never become a second LLM caller,
and that the Python side reaches capture only through the capture DB file.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UX = REPO / "ux-extension"
SERVER_SRC = UX / "server" / "src"

FORBIDDEN_DEP_PREFIXES = ("@anthropic-ai/", "openai", "@google/", "@modelcontextprotocol/")
FORBIDDEN_IMPORT = re.compile(r"""from\s+["']\./(agent|mcp|dashboard)\b|import\(\s*["']\./(agent|mcp|dashboard)\b""")


def _package_json() -> dict:
    path = UX / "package.json"
    assert path.is_file(), f"missing {path.relative_to(REPO)} — capture has no package manifest in this repo"
    return json.loads(path.read_text())


def test_capture_depends_on_no_llm_or_mcp_sdk():
    pkg = _package_json()
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    bad = sorted(d for d in deps if d.startswith(FORBIDDEN_DEP_PREFIXES))
    assert not bad, f"capture must not depend on LLM/MCP SDKs (rule 5, D-015): {bad}"


def test_old_analyzer_mcp_and_dashboard_are_gone():
    present = [p for p in (SERVER_SRC / "agent", SERVER_SRC / "mcp") if p.exists()]
    present += sorted(SERVER_SRC.glob("dashboard*"))
    assert not present, f"removed by D-015 but still present: {[str(p.relative_to(REPO)) for p in present]}"


def test_no_capture_source_imports_removed_modules():
    offenders = []
    for f in sorted(SERVER_SRC.rglob("*.ts")):
        if FORBIDDEN_IMPORT.search(f.read_text()):
            offenders.append(str(f.relative_to(REPO)))
    assert not offenders, f"imports agent/, mcp/ or dashboard: {offenders}"


def test_no_capture_source_mentions_an_llm_sdk():
    offenders = []
    for f in sorted(list(SERVER_SRC.rglob("*.ts")) + list((UX / "extension").rglob("*.js"))):
        text = f.read_text()
        if any(f'"{p}' in text or f"'{p}" in text for p in FORBIDDEN_DEP_PREFIXES):
            offenders.append(str(f.relative_to(REPO)))
    assert not offenders, f"references an LLM/MCP SDK: {offenders}"


def test_python_side_never_reaches_into_ux_extension():
    """The only link between src/tutor and capture is the capture DB file (§4.3 #5)."""
    src = REPO / "src"
    offenders = [
        str(f.relative_to(REPO))
        for f in (sorted(src.rglob("*.py")) if src.exists() else [])
        if re.search(r"ux[-_]extension", f.read_text())
    ]
    assert not offenders, f"Python code references ux-extension/: {offenders}"
