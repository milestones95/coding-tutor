"""M0 checkpoint: load one real session and make one logged LLM call (T-007, D-029).

It proves the pieces connect end to end: config → read-only loader → prompt file → client
wrapper → provider → validated output → `llm_calls.jsonl`. The smoke prompt is throwaway and
never used by a field.
"""

from pydantic import BaseModel

from tutor.capture.loader import CaptureLoader
from tutor.config import Settings
from tutor.llm import LLMClient, LLMResult, ModelRef
from tutor.logs import new_run_id
from tutor.prompts import load_prompt


class SmokeOutput(BaseModel):
    problem_slug: str


def run_smoke(settings: Settings, session_id: str, *, model: str | None = None,
              client: LLMClient | None = None) -> tuple[ModelRef, LLMResult[SmokeOutput]]:
    """Load `session_id` from the frozen copy and make one `structured()` call.

    `model` is the `--model` text. It is parsed before anything else, so a bad value fails
    before the session is loaded or a request is sent.
    """
    ref = ModelRef.parse(model) if model is not None else None
    run_id = new_run_id()
    # The frozen copy, opened immutable: the checkpoint reads the same bytes every run (D-016).
    session = CaptureLoader(settings.paths.eval_capture_db, mode="immutable", settings=settings,
                            run_id=run_id).load_session(session_id)
    client = client or LLMClient(settings)
    result = client.structured(field="smoke", prompt=load_prompt("smoke", settings.prompts.get("smoke", "v1")),
                               variables={"problem_title": session.problem.title}, output=SmokeOutput,
                               run_id=run_id, model=ref)
    return client.model_for("smoke", ref), result
