"""Failure type and explanation (eval plan "Failure reason"; architecture §6.3; D-055).

The verdict decides the type in two cases, and code applies those as rules before any model is
asked: a passed session failed in no way (`none`), and a time or memory limit means `too_slow`.
Every other status needs judgment about *why* it failed, which is the LLM's part (T-026).
"""

from typing import Literal

from pydantic import BaseModel, Field

from tutor.condense import condense, render
from tutor.config import Settings
from tutor.fields.deterministic import StatusResult, status
from tutor.llm import LLMClient, ModelRef, Usage
from tutor.models import FailureType, Session, Status
from tutor.prompts import LoadedPrompt, load_prompt

RULES: dict[Status, FailureType] = {
    Status.PASSED: FailureType.NONE,
    Status.FAILED_TOO_SLOW: FailureType.TOO_SLOW,
}


def failure_rule(status: Status) -> FailureType | None:
    """The type the verdict alone decides, or None when the LLM must decide."""
    return RULES.get(status)


# ---------------------------------------------------------------- the LLM part (T-026, D-056)

PROMPT = "failure"
ERROR_MAX_CHARS = 500   # the condenser's cap on error text (§5)


class FailureLLMOutput(BaseModel):
    # `none` is left out: only Accepted is `none`, and Accepted never reaches the model.
    failure_type: Literal["edge_case_missed", "wrong_approach", "too_slow", "implementation_bug", "did_not_finish"]
    explanation: str = Field(min_length=1)


class FailureOutput(BaseModel):
    failure_type: FailureType
    source: Literal["rule", "llm"]
    explanation: str | None


class FailureResult(BaseModel):
    output: FailureOutput
    usage: Usage | None   # None when no call was made (a passed session)
    call_id: str | None = None   # joins to llm_calls.jsonl; None when no call was made


def prompt_for(settings: Settings) -> LoadedPrompt:
    return load_prompt(PROMPT, settings.prompts.get(PROMPT, "v1"))


def _outcome(session: Session, st: StatusResult) -> str:
    if st.status is Status.NOT_SUBMITTED:
        return "Not submitted: the session ended without a submit."
    if st.status is Status.UNKNOWN:
        return "Unknown: no verdict was captured for this session."
    text = f"Final submit verdict: {st.leetcode_verdict}"
    if st.tests_total is not None:
        text += f", {st.tests_passed}/{st.tests_total} tests passed"
    final = session.final_submit
    if final is not None and final.error_detail:
        text += f". Error: {final.error_detail[:ERROR_MAX_CHARS]}"
    return text + "."


def variables(session: Session, st: StatusResult, rule: FailureType | None) -> dict[str, str]:
    decided = (f"The verdict already decides the type: {rule.value}. Answer {rule.value}, and explain the cause."
               if rule is not None else "Decide the type from the timeline.")
    return {"problem_title": session.problem.title, "difficulty": session.problem.difficulty,
            "outcome": _outcome(session, st), "decided": decided, "timeline": render(condense(session))}


def failure(session: Session, *, client: LLMClient, settings: Settings, run_id: str,
            model: ModelRef | None = None) -> FailureResult:
    st = status(session, settings=settings, run_id=run_id)
    rule = failure_rule(st.status)
    if st.status is Status.PASSED:   # nothing failed: no type to infer, no explanation (§6.3)
        return FailureResult(output=FailureOutput(failure_type=FailureType.NONE, source="rule", explanation=None),
                             usage=None)
    r = client.structured(field=PROMPT, prompt=prompt_for(settings), variables=variables(session, st, rule),
                          output=FailureLLMOutput, run_id=run_id, model=model)
    if rule is not None:   # e.g. too slow: the rule's type stands, the model only explains
        out = FailureOutput(failure_type=rule, source="rule", explanation=r.output.explanation)
    else:
        out = FailureOutput(failure_type=FailureType(r.output.failure_type), source="llm",
                            explanation=r.output.explanation)
    return FailureResult(output=out, usage=r.usage, call_id=r.call_id)
