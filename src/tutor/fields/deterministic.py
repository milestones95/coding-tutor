"""The four fields code decides: problem, time to finish, attempted at, status (§4.3, §5.1, D-014).

Nothing here calls a model. Where the captured data answers the question, code reads it
(CLAUDE.md rule 1). Status especially: the LeetCode verdict says exactly what happened, so it's
looked up in a fixed table, and a verdict the table doesn't know becomes `unknown` and is
logged, never guessed.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from tutor.condense import elapsed_min, session_times
from tutor.config import Settings
from tutor.logs import log_event
from tutor.models import Problem, Session, Status, StatusSource, Verdict

# §4.3, row for row. The verdict text is LeetCode's status_msg, kept verbatim (D-019, D-024).
STATUS_BY_VERDICT: dict[str, Status] = {
    Verdict.ACCEPTED: Status.PASSED,
    Verdict.WRONG_ANSWER: Status.FAILED_WRONG_ANSWER,
    Verdict.TIME_LIMIT_EXCEEDED: Status.FAILED_TOO_SLOW,
    Verdict.MEMORY_LIMIT_EXCEEDED: Status.FAILED_TOO_SLOW,
    Verdict.RUNTIME_ERROR: Status.FAILED_RUNTIME_ERROR,
    Verdict.COMPILE_ERROR: Status.FAILED_RUNTIME_ERROR,
    Verdict.OUTPUT_LIMIT_EXCEEDED: Status.FAILED_OUTPUT_LIMIT,  # its own status (D-022)
}


class StatusResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Status
    status_source: StatusSource
    leetcode_verdict: str | None  # verbatim; None when there is no submit
    tests_passed: int | None
    tests_total: int | None


def problem(session: Session) -> Problem:
    return session.problem


def time_to_finish(session: Session) -> float:
    """Minutes from the first event to the last captured submit, else the last event (§5.1).
    The same helper the condenser uses, so this always equals `condense(s).duration_min`."""
    t0, t_end = session_times(session)
    return elapsed_min(t_end, t0)


def attempted_at(session: Session, *, settings: Settings) -> tuple[datetime, date]:
    """(first event in UTC, its date in `time.timezone`). The local date is what "attempted on"
    means to the person practising, and it's what Part 2's day windows count."""
    t0, _ = session_times(session)
    return t0, t0.astimezone(ZoneInfo(settings.time.timezone)).date()


def status(session: Session, *, settings: Settings, run_id: str) -> StatusResult:
    final = session.final_submit
    if final is None:
        if session.submit_capture_reliable:
            return StatusResult(status=Status.NOT_SUBMITTED, status_source=StatusSource.NO_SUBMIT,
                                leetcode_verdict=None, tests_passed=None, tests_total=None)
        return StatusResult(status=Status.UNKNOWN, status_source=StatusSource.NOT_CAPTURED,
                            leetcode_verdict=None, tests_passed=None, tests_total=None)
    mapped = STATUS_BY_VERDICT.get(final.verdict)
    if mapped is None:
        log_event("unmapped_verdict", run_id=run_id, path=settings.paths.logs / "pipeline.jsonl",
                  session_id=session.session_id, verdict=final.verdict)
        mapped = Status.UNKNOWN
    return StatusResult(status=mapped, status_source=StatusSource(final.source), leetcode_verdict=final.verdict,
                        tests_passed=final.tests_passed, tests_total=final.tests_total)
