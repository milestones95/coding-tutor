"""Timeline summary: an LLM field that reads the condensed timeline (eval plan; architecture §6.3; D-060).

The model sees the rendered condensed timeline, the same text every timeline-reading field gets
(rule 3), plus the problem's title and difficulty. The verdict, runs and errors are in that
timeline: they are data. The human's labels never are. The prompt asks for 3–5 sentences; the
schema only requires a non-empty summary, so the eval can measure how often the length is broken.
"""

from pydantic import BaseModel, Field

from tutor.condense import condense, render
from tutor.config import Settings
from tutor.llm import LLMClient, LLMResult, ModelRef
from tutor.models import Session
from tutor.prompts import LoadedPrompt, load_prompt

PROMPT = "timeline"


class TimelineOutput(BaseModel):
    summary: str = Field(min_length=1, pattern=r"\S")


def prompt_for(settings: Settings) -> LoadedPrompt:
    return load_prompt(PROMPT, settings.prompts.get(PROMPT, "v1"))


def variables(session: Session) -> dict[str, str]:
    p = session.problem
    return {"problem_title": p.title, "difficulty": p.difficulty, "timeline": render(condense(session))}


def timeline(session: Session, *, client: LLMClient, settings: Settings, run_id: str,
             model: ModelRef | None = None) -> LLMResult[TimelineOutput]:
    return client.structured(field=PROMPT, prompt=prompt_for(settings), variables=variables(session),
                             output=TimelineOutput, run_id=run_id, model=model)
