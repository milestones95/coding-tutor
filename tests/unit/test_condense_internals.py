"""Builder unit tests for tutor.condense internals (T-009). Hand-built sessions, no I/O."""

from datetime import UTC, datetime, timedelta

from tutor.condense import condense, render, session_times
from tutor.models import Problem, RunEvent, Session, Snapshot, SubmitEvent

T0 = datetime(2026, 11, 1, 10, tzinfo=UTC)
P = Problem(slug="p", title="P", difficulty="Easy", tags=[], description=None)


def _s(snaps, events=()):
    return Session(session_id="u", problem=P, snapshots=[Snapshot(ts=T0 + timedelta(minutes=m), code=c,
                   language="python3") for m, c in snaps], events=list(events), submit_capture_reliable=True)


def _run(m):
    return RunEvent(ts=T0 + timedelta(minutes=m), status="Runtime Error", tests_passed=None, tests_total=None,
                    error_detail=None)


def _sub(m, source="capture_submit"):
    return SubmitEvent(ts=None if m is None else T0 + timedelta(minutes=m), verdict="Accepted", tests_passed=1,
                       tests_total=1, error_detail=None, source=source)


def test_session_times_prefers_the_last_captured_submit():
    t0, t_end = session_times(_s([(0, "a"), (9, "b")], [_sub(4), _run(7)]))
    assert (t0, t_end) == (T0, T0 + timedelta(minutes=4))


def test_session_times_ignores_backfilled_submits():
    t0, t_end = session_times(_s([(0, "a"), (3, "b")], [_run(5), _sub(None, "human_resubmit")]))
    assert t_end == T0 + timedelta(minutes=5)


def test_a_tick_exactly_at_t_end_is_included():
    c = condense(_s([(0, "a"), (4, "b")]))  # t_end = 4:00 → ticks 2, 4
    assert [m.elapsed_min for m in c.moments if m.kind == "timed"] == [4.0]


def test_a_run_before_any_snapshot_renders_no_code_yet():
    c = condense(_s([(1, "a")], [_run(0)]))
    assert c.moments[0].kind == "run" and c.moments[0].code is None and c.moments[0].code_ref is None
    assert "(no code captured yet)" in render(c)


def test_truncation_stops_as_soon_as_it_fits():
    big = "\n".join("y" * 60 for _ in range(10))
    snaps = [(0, "o")] + [(m, f"{m}\n{big}") for m in (2, 4, 6, 8)]
    full = condense(_s(snaps))
    c = condense(_s(snaps), token_budget=full.est_tokens - 1)
    dropped = [m for m in c.moments if m.kind == "timed" and m.code is None]
    assert len(dropped) == 1 and c.truncated
    assert "(code omitted to fit the token budget)" in render(c)


def test_render_depends_only_on_the_condensed_session():
    c = condense(_s([(0, "a"), (3, "b")], [_run(1)]))
    assert render(c) == render(c.model_copy())
