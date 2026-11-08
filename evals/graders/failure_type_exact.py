"""Failure-type grader (eval plan: "exact match vs. my label"). Tester-owned, deterministic.

The output is `{"failure_type": ..., "source": "rule"|"llm", "explanation": ...}`. Value 1.0 when
`failure_type` equals the case's expected type exactly, else 0.0. A missing type scores 0.0. The
explanation is not graded here: that needs the M4 judge (D-052).
"""

from evals.graders.base import Grade, GradeContext


class FailureTypeExact:
    name = "failure_type_exact"
    version = "v1"
    kind = "deterministic"

    def grade(self, case, output: dict, ctx: GradeContext) -> list[Grade]:
        got = (output or {}).get("failure_type")
        want = case.expected.get("failure_type")
        return [Grade(metric="failure_type_exact", value=1.0 if got is not None and got == want else 0.0,
                      detail=f"predicted {got!r} vs expected {want!r}")]
