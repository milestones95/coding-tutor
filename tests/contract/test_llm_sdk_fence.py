"""SDK fence — architecture §4.3 #2, §6.1; rule 5. Tester-owned; kept for the life of the project
(`/test write T-006`, 2026-11-03).

Every LLM call goes through the one client wrapper, so only `src/tutor/llm/adapters/` may import
a provider SDK. Python code anywhere else in the repo (`src/`, `evals/`, `scripts/`) may not —
including the synthetic-session generator, which also goes through the wrapper (D-017).
Checked on the parsed import statements, plus dynamic imports by string.
"""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOTS = [REPO / "src", REPO / "evals", REPO / "scripts"]
ALLOWED = REPO / "src" / "tutor" / "llm" / "adapters"
SDKS = ("openai", "anthropic", "google.genai", "google.generativeai", "google.ai", "litellm", "mistralai", "cohere")
DYNAMIC = re.compile(r"""(import_module|__import__)\(\s*["'](%s)\b""" % "|".join(re.escape(s) for s in SDKS))


def _is_sdk(module: str) -> bool:
    return any(module == s or module.startswith(s + ".") for s in SDKS)


def violations(path: Path) -> list[str]:
    src = path.read_text()
    out = []
    for node in ast.walk(ast.parse(src, filename=str(path))):
        if isinstance(node, ast.Import):
            out += [f"{path}:{node.lineno}: import {a.name}" for a in node.names if _is_sdk(a.name)]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            # `from google import genai` names the SDK only once module and name are joined.
            if _is_sdk(node.module) or any(_is_sdk(f"{node.module}.{a.name}") for a in node.names):
                out.append(f"{path}:{node.lineno}: from {node.module} import …")
    out += [f"{path}: dynamic import of {m.group(2)}" for m in DYNAMIC.finditer(src)]
    return out


def _python_files():
    for root in ROOTS:
        if root.exists():
            yield from (p for p in sorted(root.rglob("*.py")) if "__pycache__" not in p.parts)


def test_only_adapters_import_a_provider_sdk():
    bad = []
    for f in _python_files():
        if ALLOWED in f.parents:
            continue
        bad += violations(f)
    assert not bad, "provider SDK imported outside tutor/llm/adapters/:\n" + "\n".join(bad)


def test_the_fence_catches_what_it_should(tmp_path):
    """Grade the fence: hand-made files whose right answer is known."""
    caught = ["import openai", "from openai import OpenAI", "import anthropic as a",
              "from google import genai", "import google.genai", "from google.genai import types",
              "import importlib\nimportlib.import_module('openai')", "x = __import__(\"anthropic\")"]
    allowed = ["from tutor.llm import LLMClient", "import openapi_spec", "# we call openai via the wrapper",
               "from .adapters import openai", "s = 'openai:gpt-5.5'"]
    for i, text in enumerate(caught):
        p = tmp_path / f"caught_{i}.py"
        p.write_text(text + "\n")
        assert violations(p), text
    for i, text in enumerate(allowed):
        p = tmp_path / f"allowed_{i}.py"
        p.write_text(text + "\n")
        assert not violations(p), text
