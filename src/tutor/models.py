"""Inference-side data models (architecture §4.1, D-024).

Everything captured enters the project as one of these, validated at the loader boundary, so
nothing downstream ever reads a raw database row. All models are frozen: a `Session` is a
fact about the past, and code that "fixes" one in place would make two readers disagree.

Timestamps must carry a timezone and are normalised to UTC. A naive datetime is rejected
rather than guessed at, because guessing the zone silently shifts "attempted at" by hours.
"""

from datetime import UTC
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field


class Verdict(StrEnum):
    """LeetCode's submit verdicts as the status mapping knows them (§4.2).

    `SubmitEvent.verdict` is the verbatim text, not this enum (D-024): LeetCode can send text
    that isn't listed, and the loader must not crash on it. Status mapping (M1) uses this list.
    """

    ACCEPTED = "Accepted"
    WRONG_ANSWER = "Wrong Answer"
    TIME_LIMIT_EXCEEDED = "Time Limit Exceeded"
    RUNTIME_ERROR = "Runtime Error"
    MEMORY_LIMIT_EXCEEDED = "Memory Limit Exceeded"
    OUTPUT_LIMIT_EXCEEDED = "Output Limit Exceeded"
    COMPILE_ERROR = "Compile Error"


class Status(StrEnum):
    """Session status (§4.3, D-014, D-022). A fact read from the verdict, never an LLM guess."""

    PASSED = "passed"
    FAILED_WRONG_ANSWER = "failed_wrong_answer"
    FAILED_TOO_SLOW = "failed_too_slow"
    FAILED_OUTPUT_LIMIT = "failed_output_limit"
    FAILED_RUNTIME_ERROR = "failed_runtime_error"
    NOT_SUBMITTED = "not_submitted"
    UNKNOWN = "unknown"


class StatusSource(StrEnum):
    """Where a status came from (§3.2 `sessions.status_source`)."""

    CAPTURE_SUBMIT = "capture_submit"
    HUMAN_RESUBMIT = "human_resubmit"
    NO_SUBMIT = "no_submit"
    NOT_CAPTURED = "not_captured"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# Aware (a naive datetime fails validation) and normalised to UTC.
UtcDatetime = Annotated[AwareDatetime, AfterValidator(lambda v: v.astimezone(UTC))]


class Problem(_Model):
    slug: str
    title: str
    difficulty: Literal["Easy", "Medium", "Hard"]
    tags: list[str]
    description: str | None  # problem statement text; None if never opened


class Snapshot(_Model):
    ts: UtcDatetime
    code: str
    language: str


class RunEvent(_Model):
    kind: Literal["run"] = "run"
    ts: UtcDatetime
    status: str  # 'Passed sample tests', 'Wrong Answer (sample tests)', …
    tests_passed: int | None
    tests_total: int | None
    error_detail: str | None


class SubmitEvent(_Model):
    kind: Literal["submit"] = "submit"
    ts: UtcDatetime | None  # None for a backfilled verdict (time not captured)
    verdict: str  # verbatim LeetCode text (D-024)
    tests_passed: int | None
    tests_total: int | None
    error_detail: str | None
    source: Literal["capture_submit", "human_resubmit"]


Event = Annotated[RunEvent | SubmitEvent, Field(discriminator="kind")]


class Session(_Model):
    session_id: str
    problem: Problem
    snapshots: list[Snapshot] = Field(min_length=1)  # sorted by ts; non-attempts are excluded (§4.4)
    events: list[Event]  # sorted by ts; backfilled submits last
    submit_capture_reliable: bool  # session started on/after capture.submits_reliable_since

    @property
    def final_submit(self) -> SubmitEvent | None:
        """The last submit in event order, or None if the session has none."""
        return next((e for e in reversed(self.events) if isinstance(e, SubmitEvent)), None)


# ---------------------------------------------------------------- condensed timeline (§4.1, §5, D-034)


class ChangeSummary(_Model):
    """How a kept snapshot's code differs from the previous one shown (§5.3)."""

    lines_added: int
    lines_removed: int
    changed_fraction: float  # 0..1, rounded to 2 decimals
    rewrite: bool  # changed_fraction >= 0.5


class Moment(_Model):
    """One line of the condensed timeline: a point worth showing a model."""

    elapsed_min: float  # from session start, 1 decimal
    ts: UtcDatetime | None  # None only for a backfilled submit (time not captured)
    kind: Literal["opened", "timed", "run", "submit", "final"]
    code: str | None  # None when unchanged since the Moment at code_ref, or dropped for the budget
    code_ref: int | None  # index into CondensedSession.moments of the Moment whose code applies
    change: ChangeSummary | None  # vs the previous Moment that showed code; None for 'opened'
    run: RunEvent | None = None  # kind='run'
    submit: SubmitEvent | None = None  # kind='submit' (D-034)
    snapshot_lag_s: float | None = None  # run/submit: seconds from the snapshot shown to the event


class CondensedSession(_Model):
    """What every LLM field reads (rule 3): the output of the one condenser."""

    session_id: str
    condenser_version: str
    problem: Problem
    language: str  # the session's language, for fencing code in the render (D-035)
    duration_min: float  # = time to finish (§5.1)
    moments: list[Moment]
    truncated: bool  # True when timed code was dropped to fit the token budget
    est_tokens: int  # len(render(...)) // 4 — an estimate, labelled as one
