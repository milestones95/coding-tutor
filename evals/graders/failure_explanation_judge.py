"""Failure-explanation judge (eval plan "Failure explanation: consistent with the real failure, no
invented causes"; architecture §8.4; D-052, D-065). Tester-owned. An `llm_judge` grader: one
structured call per explanation through `ctx.client`, with `prompts/judges/failure_explanation/vN.md`.

Two items, each with a reason and `met`: `consistent` (the cause agrees with the human's failure
type and key facts) and `no_invented_cause` (every concrete detail is in the timeline).
Grades: `explanation_checklist` (the share of the two items met), then `explanation.<item>`.
A passed session has no explanation (§6.3), so it gets no grades: there is nothing to judge.

The judge reads the case's `expected` (the human's failure type and key facts) and the session's
rendered condensed timeline from `ctx.session`. It is a grader: it may read labels; the field
never does (rule 1).
"""

from typing import Any

from pydantic import BaseModel, Field

from evals.graders.base import Grade, GradeContext

ITEMS = ("consistent", "no_invented_cause")


class Item(BaseModel):
    reason: str = Field(min_length=1)
    met: bool


class FailureExplanationJudgeOutput(BaseModel):
    consistent: Item
    no_invented_cause: Item


def variables(expected: dict, timeline: str, explanation: str) -> dict[str, str]:
    return {"failure_type": expected["failure_type"],
            "key_facts": "; ".join(f"({n}) {k}" for n, k in enumerate(expected.get("key_facts") or [], 1)),
            "timeline": timeline, "explanation": explanation}


def score(judged: dict[str, bool]) -> list[Grade]:
    met = sum(judged[i] for i in ITEMS)
    return ([Grade(metric="explanation_checklist", value=met / len(ITEMS), detail=f"{met}/{len(ITEMS)} items met")]
            + [Grade(metric=f"explanation.{i}", value=1.0 if judged[i] else 0.0) for i in ITEMS])


class FailureExplanationJudge:
    name, version, kind, field = "failure-explanation-judge", "v1", "llm_judge", "failure_explanation_judge"

    def __init__(self) -> None:
        self.run_id = "unset"
        self.last_usage: Any = None
        self.last_output: FailureExplanationJudgeOutput | None = None

    def judge(self, expected: dict, timeline: str, explanation: str, *, client: Any) -> FailureExplanationJudgeOutput:
        from tutor.prompts import load_prompt

        self.last_usage = None
        r = client.structured(field=self.field, prompt=load_prompt("judges/failure_explanation", self.version),
                              variables=variables(expected, timeline, explanation),
                              output=FailureExplanationJudgeOutput, run_id=self.run_id)
        self.last_usage, self.last_output = r.usage, r.output
        return r.output

    def grade(self, case: Any, output: dict, ctx: GradeContext) -> list[Grade]:
        from tutor.condense import condense, render

        self.last_usage = None
        explanation = (output or {}).get("explanation")
        if not explanation:
            return []
        if ctx is None or ctx.client is None or ctx.session is None:
            raise ValueError("the failure-explanation judge needs ctx.client and ctx.session")
        out = self.judge(case.expected, render(condense(ctx.session)), explanation, client=ctx.client)
        return score({i: getattr(out, i).met for i in ITEMS})
