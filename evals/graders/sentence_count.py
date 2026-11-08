"""Timeline length grader (eval plan "Summary checklist": "5 sentences or fewer"). Tester-owned,
deterministic: code counts sentences, so the judge is never trusted with arithmetic (T-033).

The output is `{"summary": str}`. Value 1.0 when the summary has 1–5 sentences, else 0.0 (an empty
or missing summary scores 0.0). The other checklist items need the judge (T-033).

A sentence ends at `.`, `!` or `?` followed by whitespace and then a capital letter, digit, quote or
bracket, or at the end of the text. So "16.6 min", "59/90", "e.g. a stack" and "nums[i]." inside a
sentence don't split it.
"""

import re

from evals.graders.base import Grade, GradeContext

MAX_SENTENCES = 5
_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[`])")


def count_sentences(text: str) -> int:
    text = (text or "").strip()
    if not text:
        return 0
    return len([s for s in _END.split(text) if s.strip()])


class SentenceCount:
    name = "sentence_count"
    version = "v1"
    kind = "deterministic"

    def grade(self, case, output: dict, ctx: GradeContext) -> list[Grade]:
        n = count_sentences((output or {}).get("summary") or "")
        return [Grade(metric="at_most_5_sentences", value=1.0 if 1 <= n <= MAX_SENTENCES else 0.0,
                      detail=f"{n} sentence(s)")]
