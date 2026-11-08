"""Timeline judge (eval plan "Summary checklist", "Checking the judge"; architecture §8.4; D-062).
Tester-owned. An `llm_judge` grader: one structured call per summary through `ctx.client`, with the
prompt `prompts/judges/timeline/vN.md`.

Six checklist items. Five are judged by the model, each with a reason and `met`; the sixth,
"5 sentences or fewer", is counted by code (`sentence_count`), never by the judge.
"no invented correction" doesn't apply when the person did switch approach (the account says
corrected), so it is left out of that case's score rather than counted as met.

Grades: `timeline_checklist` (the share of applicable items met, the eval plan's metric, first so
the runner's `accuracy` reads it), then `checklist.<item>` for each applicable item.
The judge reads the case's `expected` (the human's account) and the session's rendered condensed
timeline from `ctx.session`. It is a grader: it may read labels; the field never does (rule 1).
"""

from typing import Any

from pydantic import BaseModel, Field

from evals.graders.base import Grade, GradeContext
from evals.graders.sentence_count import MAX_SENTENCES, count_sentences

ITEMS = ("approaches", "first_approach", "no_invented_correction", "final_and_outcome", "no_invented_events")


class Item(BaseModel):
    reason: str = Field(min_length=1)
    met: bool


class TimelineJudgeOutput(BaseModel):
    approaches: Item
    first_approach: Item
    no_invented_correction: Item
    final_and_outcome: Item
    no_invented_events: Item


def describe_course_correction(cc: dict) -> str:
    if cc.get("first_approach_on_track"):
        return "it was on the right track."
    if cc.get("corrected"):
        return f"it was not on the right track; they switched to a different approach at about minute {cc.get('at_min')}."
    return "it was not on the right track, and they never switched to a different approach."


def applicable(expected: dict) -> tuple[str, ...]:
    """The judged items that apply to this case: 'no invented correction' needs an approach that never changed."""
    corrected = expected["checklist"]["course_correction"].get("corrected") is True
    return tuple(i for i in ITEMS if not (corrected and i == "no_invented_correction"))


def variables(expected: dict, timeline: str, summary: str) -> dict[str, str]:
    ch = expected["checklist"]
    return {"approaches": "; ".join(f"({n}) {a}" for n, a in enumerate(ch["approaches"], 1)),
            "course_correction": describe_course_correction(ch["course_correction"]),
            "final_approach": ch["final_approach"], "outcome": ch["outcome"],
            "timeline": timeline, "summary": summary}


def score(expected: dict, judged: dict[str, bool], summary: str) -> list[Grade]:
    """Turn the judge's per-item answers plus the code-counted length into grades."""
    items = {i: judged[i] for i in applicable(expected)}
    n = count_sentences(summary)
    items["at_most_5_sentences"] = 1 <= n <= MAX_SENTENCES
    met = sum(items.values())
    return ([Grade(metric="timeline_checklist", value=met / len(items), detail=f"{met}/{len(items)} items met")]
            + [Grade(metric=f"checklist.{i}", value=1.0 if v else 0.0) for i, v in items.items()])


class TimelineJudge:
    name, version, kind, field = "timeline-judge", "v1", "llm_judge", "timeline_judge"

    def __init__(self) -> None:
        self.run_id = "unset"
        self.last_usage: Any = None
        self.last_output: TimelineJudgeOutput | None = None

    def judge(self, expected: dict, timeline: str, summary: str, *, client: Any) -> TimelineJudgeOutput:
        from tutor.prompts import load_prompt

        self.last_usage = None
        r = client.structured(field=self.field, prompt=load_prompt("judges/timeline", self.version),
                              variables=variables(expected, timeline, summary), output=TimelineJudgeOutput,
                              run_id=self.run_id)
        self.last_usage, self.last_output = r.usage, r.output
        return r.output

    def grade(self, case: Any, output: dict, ctx: GradeContext) -> list[Grade]:
        from tutor.condense import condense, render

        summary = (output or {}).get("summary") or ""
        if ctx is None or ctx.client is None or ctx.session is None:
            raise ValueError("the timeline judge needs ctx.client and ctx.session")
        out = self.judge(case.expected, render(condense(ctx.session)), summary, client=ctx.client)
        return score(case.expected, {i: getattr(out, i).met for i in ITEMS}, summary)
