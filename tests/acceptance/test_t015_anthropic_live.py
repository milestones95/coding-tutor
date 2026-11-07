"""Acceptance for T-015 Done-when 3: one real, logged call to the generator model.

Tester-owned (`/test write T-015`, 2026-11-07). Marked `llm`, so it is deselected by default:
    uv run pytest -m llm tests/acceptance/test_t015_anthropic_live.py      # well under $0.01
"""

import json

import pytest
from pydantic import BaseModel


class Slug(BaseModel):
    problem_slug: str


@pytest.mark.llm
def test_a_real_structured_call_to_the_generator_model_is_logged_with_cost(tmp_path, monkeypatch):
    from tutor.config import load_settings
    from tutor.llm import LLMClient, ModelRef
    from tutor.prompts import load_prompt

    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    (tmp_path / "p" / "slug").mkdir(parents=True)
    (tmp_path / "p" / "slug" / "v1.md").write_text(
        "---\nname: slug\nversion: v1\nfield: smoke\nvariables: [title]\noutput_schema: Slug\n---\n"
        'Give the LeetCode URL slug for the problem titled "$title". Answer with JSON only.\n')
    settings = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")})
    r = LLMClient(settings).structured(field="smoke", prompt=load_prompt("slug", "v1", root=tmp_path / "p"),
                                       variables={"title": "Two Sum"}, output=Slug, run_id="t015-live",
                                       model=ModelRef.parse(settings.llm.generator))
    assert r.output.problem_slug
    [line] = [json.loads(x) for x in (tmp_path / "logs" / "llm_calls.jsonl").read_text().splitlines()]
    assert (line["provider"], line["model"], line["outcome"]) == ("anthropic", "claude-opus-5-5", "ok")
    assert line["cost_usd"] > 0 and line["input_tokens"] > 0
