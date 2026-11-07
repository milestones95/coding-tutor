"""Algorithm-type grader (eval plan: "any overlap with my labels counts"). Tester-owned, deterministic.

The output is `{"labels": [...]}`. Value 1.0 if it shares at least one label with the case's
expected labels, else 0.0. An empty or missing output scores 0.0: predicting nothing is not a hit.
"""

from evals.graders.base import Grade, GradeContext


class AlgorithmOverlap:
    name = "algorithm_overlap"
    version = "v1"
    kind = "deterministic"

    def grade(self, case, output: dict, ctx: GradeContext) -> list[Grade]:
        got = set((output or {}).get("labels") or [])
        want = set(case.expected.get("labels") or [])
        hit = bool(got & want)
        return [Grade(metric="algorithm_overlap", value=1.0 if hit else 0.0,
                      detail=f"predicted {sorted(got)} vs expected {sorted(want)}")]
