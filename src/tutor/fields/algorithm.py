"""Algorithm type: an LLM field that reads the final code (eval plan; architecture §6.3; D-054).

The model sees the final snapshot's code plus the problem's title, difficulty and tags. Tags are
hints about the problem, not answers about this code. It never sees the verdict, the runs or the
earlier snapshots: the label describes what the code at the end does, and outcome information
would only tempt the model to label the problem instead.
"""

from pydantic import BaseModel, Field

from tutor.config import Settings
from tutor.llm import LLMClient, LLMResult, ModelRef
from tutor.models import AlgorithmLabel, Session
from tutor.prompts import LoadedPrompt, load_prompt

PROMPT = "algorithm"


class AlgorithmOutput(BaseModel):
    algorithms: list[AlgorithmLabel] = Field(min_length=1, max_length=2)


def prompt_for(settings: Settings) -> LoadedPrompt:
    return load_prompt(PROMPT, settings.prompts.get(PROMPT, "v1"))


def variables(session: Session) -> dict[str, str]:
    p = session.problem
    return {"problem_title": p.title, "difficulty": p.difficulty,
            "tags": ", ".join(p.tags) if p.tags else "(none)", "final_code": session.snapshots[-1].code}


def algorithm(session: Session, *, client: LLMClient, settings: Settings, run_id: str,
              model: ModelRef | None = None) -> LLMResult[AlgorithmOutput]:
    return client.structured(field=PROMPT, prompt=prompt_for(settings), variables=variables(session),
                             output=AlgorithmOutput, run_id=run_id, model=model)
