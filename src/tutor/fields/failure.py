"""Failure type and explanation (eval plan "Failure reason"; architecture §6.3; D-055).

The verdict decides the type in two cases, and code applies those as rules before any model is
asked: a passed session failed in no way (`none`), and a time or memory limit means `too_slow`.
Every other status needs judgment about *why* it failed, which is the LLM's part (T-026).
"""

from tutor.models import FailureType, Status

RULES: dict[Status, FailureType] = {
    Status.PASSED: FailureType.NONE,
    Status.FAILED_TOO_SLOW: FailureType.TOO_SLOW,
}


def failure_rule(status: Status) -> FailureType | None:
    """The type the verdict alone decides, or None when the LLM must decide."""
    return RULES.get(status)
