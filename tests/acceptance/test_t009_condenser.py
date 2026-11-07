"""Acceptance tests for T-009: condenser `c1` (architecture §4.1, §5; eval-plan condensing tests).

Tester-owned (`/test write T-009`, 2026-11-03). Black-box against:

    tutor.condense: CONDENSER_VERSION ("c1"), CondenseBudgetError,
        condense(session, *, interval_s=120, error_max_chars=500, token_budget=16_000) -> CondensedSession
        render(c) -> str
        change_summary(prev, new) -> ChangeSummary
    tutor.models: ChangeSummary, Moment, CondensedSession

Plus the gaps the human settled (D-034):
    - `Moment.submit: SubmitEvent | None` carries a submit's verdict (kind='submit').
    - FINAL is the last timed Moment: its ts is the latest snapshot or event timestamp, its code
      the last snapshot's. Only backfilled submits (ts=None) follow it; they take FINAL's elapsed
      and point at the final code.
    - A rewrite renders as " · REWRITE" at the end of the change line.
    - A timed Moment's ts is its tick (t0 + k·interval_s, k ≥ 1, ticks ≤ t_end inclusive).
    - `code_ref` is an index into `moments`. A Moment with code=None has change=None, except a
      timed Moment whose code was dropped for the budget, which keeps its change.

Sessions are hand-built, so every expected value below is worked out by hand in a comment.
"""

from datetime import UTC, datetime, timedelta

import pytest

from tutor.models import Problem, RunEvent, Session, Snapshot, SubmitEvent

T0 = datetime(2026, 11, 1, 10, 0, 0, tzinfo=UTC)
PROBLEM = Problem(slug="probe-problem", title="Probe Problem", difficulty="Medium",
                  tags=["array", "hash-table"], description="Given nums, return something.")


def at(minutes=0, seconds=0):
    return T0 + timedelta(minutes=minutes, seconds=seconds)


def snap(t, code, language="python3"):
    return Snapshot(ts=t, code=code, language=language)


def run(t, status="Wrong Answer (sample tests)", passed=None, total=None, error=None):
    return RunEvent(ts=t, status=status, tests_passed=passed, tests_total=total, error_detail=error)


def submit(t, verdict="Accepted", passed=5, total=5, error=None, source="capture_submit"):
    return SubmitEvent(ts=t, verdict=verdict, tests_passed=passed, tests_total=total, error_detail=error,
                       source=source)


def session(snapshots, events=(), sid="s1"):
    return Session(session_id=sid, problem=PROBLEM, snapshots=list(snapshots), events=list(events),
                   submit_capture_reliable=True)


def cz():
    import tutor.condense

    return tutor.condense


def summary(c):
    """(kind, elapsed_min, has_code, code_ref) per Moment: the shape the hand-worked answers use."""
    return [(m.kind, m.elapsed_min, m.code is not None, m.code_ref) for m in c.moments]


V0 = "class Solution:\n    pass"
V1 = "class Solution:\n    def f(self, nums):\n        return 0"
V2 = "class Solution:\n    def f(self, nums):\n        seen = {}\n        return 0"
V3 = "class Solution:\n    def f(self, nums):\n        seen = {}\n        return len(seen)"

# S1 — t0 = 10:00:00. Snapshots 0:00 V0, 1:30 V1, 3:10 V2, 5:00 V2 (no change), 7:30 V3.
# Runs at 3:40 (snapshot 3:10 → lag 30 s) and 6:00 (snapshot 5:00 → lag 60 s); submit at 8:00.
# t_end = 8:00 → ticks 2, 4, 6, 8.
#   0.0 opened V0
#   2.0 timed   → latest snapshot 1:30 V1, changed      → kept with code
#   3.7 run     → snapshot 3:10 V2, changed             → code
#   4.0 tick    → snapshot 3:10 V2 = last kept          → skipped
#   6.0 tick    → snapshot 5:00 V2 = last kept          → skipped
#   6.0 run     → V2 unchanged                          → code_ref 2
#   8.0 timed   → snapshot 7:30 V3, changed             → code
#   8.0 submit  → V3 unchanged (tie: timed < submit)    → code_ref 4
#   8.0 final   → latest ts is the submit at 8:00, V3   → code_ref 4
S1 = session(
    [snap(at(0), V0), snap(at(1, 30), V1), snap(at(3, 10), V2), snap(at(5), V2), snap(at(7, 30), V3)],
    [run(at(3, 40), passed=0, total=2, error="Output: [0] | Expected: [1]"),
     run(at(6), status="Passed sample tests", passed=2, total=2),
     submit(at(8))],
)
S1_EXPECTED = [("opened", 0.0, True, None), ("timed", 2.0, True, None), ("run", 3.7, True, None),
               ("run", 6.0, False, 2), ("timed", 8.0, True, None), ("submit", 8.0, False, 4),
               ("final", 8.0, False, 4)]

# S2 — no captured submit; one backfilled verdict. Snapshots 0:00 V0, 3:00 V1; runs at 1:00 and 4:00.
# t_end = last event = 4:00 → ticks 2, 4.
#   0.0 opened V0
#   1.0 run    → snapshot 0:00 V0 unchanged → code_ref 0
#   2.0 tick   → snapshot 0:00 V0           → skipped
#   4.0 timed  → snapshot 3:00 V1, changed  → code
#   4.0 run    → V1 unchanged               → code_ref 2
#   4.0 final  → latest ts 4:00, V1         → code_ref 2
#   (time not captured) submit → FINAL's elapsed, final code → code_ref 2
S2 = session(
    [snap(at(0), V0), snap(at(3), V1)],
    [run(at(1), status="Time Limit Exceeded"), run(at(4), passed=0, total=2),
     submit(None, verdict="Wrong Answer", passed=59, total=90, source="human_resubmit")],
    sid="s2",
)
S2_EXPECTED = [("opened", 0.0, True, None), ("run", 1.0, False, 0), ("timed", 4.0, True, None),
               ("run", 4.0, False, 2), ("final", 4.0, False, 2), ("submit", 4.0, False, 2)]


# ---------------------------------------------------------------- the worked sessions, exactly


def test_s1_moments_match_the_hand_worked_timeline():
    c = cz().condense(S1)
    assert summary(c) == S1_EXPECTED
    assert c.duration_min == 8.0
    assert c.condenser_version == cz().CONDENSER_VERSION == "c1"
    assert c.session_id == "s1" and c.problem == PROBLEM


def test_s2_backfilled_submit_follows_final():
    c = cz().condense(S2)
    assert summary(c) == S2_EXPECTED
    last = c.moments[-1]
    assert last.ts is None and last.submit is not None
    assert (last.submit.verdict, last.submit.source) == ("Wrong Answer", "human_resubmit")
    assert c.duration_min == 4.0, "no captured submit: t_end is the last event"


# ---------------------------------------------------------------- eval plan: every run and submit is kept


def test_every_run_and_submit_is_kept_with_its_result():
    # Code never changes, so nothing but the events justifies these Moments.
    events = [run(at(m), status=s) for m, s in [(1, "Wrong Answer (sample tests)"), (2, "Runtime Error"),
                                                 (3, "Time Limit Exceeded"), (4, "Passed sample tests"),
                                                 (5, "Compile Error")]]
    events += [submit(at(6), verdict="Wrong Answer", passed=3, total=10), submit(at(7))]
    c = cz().condense(session([snap(at(0), V0)], events))
    runs = [m for m in c.moments if m.kind == "run"]
    subs = [m for m in c.moments if m.kind == "submit"]
    assert [m.run.status for m in runs] == ["Wrong Answer (sample tests)", "Runtime Error",
                                           "Time Limit Exceeded", "Passed sample tests", "Compile Error"]
    assert [(m.submit.verdict, m.submit.tests_passed, m.submit.tests_total) for m in subs] == \
        [("Wrong Answer", 3, 10), ("Accepted", 5, 5)]
    assert all(m.run is None for m in subs) and all(m.submit is None for m in runs)


# ---------------------------------------------------------------- eval plan: a snapshot every 2 minutes while the code changes


def test_a_snapshot_every_two_minutes_while_the_code_changes():
    # A change every minute for 10 minutes; no events. t_end = last snapshot (10:00) → ticks 2..10.
    snaps = [snap(at(m), f"x = {m}") for m in range(11)]
    c = cz().condense(session(snaps))
    timed = [m for m in c.moments if m.kind == "timed"]
    assert [m.elapsed_min for m in timed] == [2.0, 4.0, 6.0, 8.0, 10.0]
    assert [m.code for m in timed] == ["x = 2", "x = 4", "x = 6", "x = 8", "x = 10"], \
        "each tick takes the latest snapshot at or before it"
    assert summary(c)[-1] == ("final", 10.0, False, len(c.moments) - 2)


def test_no_timed_snapshot_while_the_code_does_not_change():
    c = cz().condense(session([snap(at(0), V0), snap(at(9), V0), snap(at(10), V0)]))
    assert [m.kind for m in c.moments] == ["opened", "final"]


def test_opened_and_final_are_always_present():
    c = cz().condense(session([snap(at(0), V0)]))
    assert [m.kind for m in c.moments] == ["opened", "final"]
    assert c.moments[0].change is None, "opened has no change summary"


def test_run_and_submit_moments_carry_the_snapshot_lag():
    c = cz().condense(S1)
    runs = [m for m in c.moments if m.kind == "run"]
    assert [m.snapshot_lag_s for m in runs] == [30.0, 60.0]


def test_every_code_ref_points_at_a_moment_with_code():
    for s in (S1, S2):
        c = cz().condense(s)
        for m in c.moments:
            if m.code is None and m.code_ref is not None:
                assert c.moments[m.code_ref].code is not None


def test_change_is_against_the_previous_moment_with_code():
    c = cz().condense(S1)
    change_summary = cz().change_summary
    assert c.moments[1].change == change_summary(V0, V1)
    assert c.moments[2].change == change_summary(V1, V2)
    assert c.moments[4].change == change_summary(V2, V3)
    assert all(m.change is None for m in c.moments if m.code is None)


# ---------------------------------------------------------------- eval plan: elapsed times match the raw timestamps


def test_elapsed_times_match_the_raw_timestamps():
    c = cz().condense(S1)
    for m in c.moments:
        if m.ts is not None and m.kind != "timed":
            assert m.elapsed_min == round((m.ts - T0).total_seconds() / 60, 1)
    assert [m.ts for m in c.moments if m.kind == "timed"] == [at(2), at(8)], "a timed Moment is at its tick"


def test_t0_is_the_earliest_of_snapshots_and_events():
    # A run 30 s before the first snapshot: t0 is the run.
    c = cz().condense(session([snap(at(1), V0), snap(at(3), V1)], [run(at(0, 30))]))
    assert c.moments[0].kind in ("opened", "run")
    assert c.duration_min == 2.5, "t_end = last snapshot at 3:00, t0 = run at 0:30"


def test_duration_ends_at_the_last_captured_submit_and_final_comes_last():
    # Submit at 6:00, then more typing and a run at 9:00: time to finish stops at the submit.
    s = session([snap(at(0), V0), snap(at(5), V1), snap(at(8), V2)],
                [submit(at(6), verdict="Wrong Answer", passed=1, total=9), run(at(9))])
    c = cz().condense(s)
    assert c.duration_min == 6.0
    final = c.moments[-1]
    assert final.kind == "final" and final.elapsed_min == 9.0
    # The 9:00 run already showed V2 (snapshot 8:00), so FINAL points back at it.
    assert (final.code if final.code is not None else c.moments[final.code_ref].code) == V2
    assert max(m.elapsed_min for m in c.moments if m.kind == "timed") <= 6.0, "ticks stop at t_end"


def test_ties_order_timed_run_submit_final():
    # Run and submit both exactly on the 2:00 tick, with changed code at 2:00.
    s = session([snap(at(0), V0), snap(at(2), V1)], [run(at(2)), submit(at(2))])
    assert [m.kind for m in cz().condense(s).moments] == ["opened", "timed", "run", "submit", "final"]


# ---------------------------------------------------------------- change_summary (§5.3)


@pytest.mark.parametrize("prev,new,expected", [
    # 1 line replaced out of 4: ratio = 2·3/8 = 0.75 → 0.25 changed
    ("a\nb\nc\nd", "a\nb\nX\nd", (1, 1, 0.25, False)),
    ("a\nb", "a\nb", (0, 0, 0.0, False)),
    # 2 lines appended to 2: ratio = 2·2/6 = 0.667 → 0.33
    ("a\nb", "a\nb\nc\nd", (2, 0, 0.33, False)),
    # everything new: ratio 0 → 1.0, a rewrite
    ("a\nb", "x\ny\nz", (3, 2, 1.0, True)),
    # exactly half: ratio = 2·2/8 = 0.5 → 0.5 changed → rewrite (≥ 0.5)
    ("a\nb\nc\nd", "a\nb\nx\ny", (2, 2, 0.5, True)),
])
def test_change_summary_follows_section_5_3(prev, new, expected):
    cs = cz().change_summary(prev, new)
    assert (cs.lines_added, cs.lines_removed, cs.changed_fraction, cs.rewrite) == expected


# ---------------------------------------------------------------- render (§5.5)


def test_render_header_lines():
    text = cz().render(cz().condense(S1))
    lines = text.splitlines()
    assert lines[0] == "Problem: Probe Problem (Medium) · tags: array, hash-table"
    assert lines[1].startswith("Session: 8.0 min · 2 runs · ")


def test_render_shows_each_moment_as_section_5_5_does():
    text = cz().render(cz().condense(S1))
    assert "[0.0 min] CODE WHEN THE PAGE OPENED" in text
    cs = cz().change_summary(V0, V1)
    assert (f"[2.0 min] SNAPSHOT · +{cs.lines_added} −{cs.lines_removed} lines · "
            f"{round(cs.changed_fraction * 100)}% changed") in text
    assert "[3.7 min] RUN · Wrong Answer (sample tests)" in text
    assert "0/2 passed" in text and "code as of 30.0 s earlier" in text
    assert "Output: [0] | Expected: [1]" in text
    assert "(code unchanged since 3.7 min)" in text, "the 6.0 run points back at the 3.7 run's code"
    assert "[8.0 min] SUBMIT · Accepted · 5/5 tests passed" in text
    assert "[8.0 min] FINAL CODE" in text
    assert "```python3\n" + V0 + "\n```" in text, "code is fenced with the session language"


def test_render_backfilled_submit_line():
    text = cz().render(cz().condense(S2))
    assert "SUBMIT (time not captured) · Wrong Answer · 59/90 tests passed" in text
    assert text.index("FINAL CODE") < text.index("SUBMIT (time not captured)")


def test_render_marks_a_rewrite():
    # V0 → completely different code: changed_fraction 1.0, rewrite.
    s = session([snap(at(0), "a = 1\nb = 2"), snap(at(1), "x = 9\ny = 8\nz = 7")])
    text = cz().render(cz().condense(s))
    assert "100% changed · REWRITE" in text
    s = session([snap(at(0), "a\nb\nc\nd"), snap(at(1), "a\nb\nX\nd")])
    assert "REWRITE" not in cz().render(cz().condense(s)), "25% changed is not a rewrite"


def test_render_truncates_long_errors():
    err = "E" * 500 + "TAIL-SHOULD-NOT-APPEAR" + "e" * 78
    c = cz().condense(session([snap(at(0), V0)], [run(at(1), status="Runtime Error", error=err)]),
                      error_max_chars=500)
    text = cz().render(c)
    assert "E" * 500 + "… [truncated]" in text
    assert "TAIL-SHOULD-NOT-APPEAR" not in text


def test_est_tokens_is_render_length_over_four():
    c = cz().condense(S1)
    assert c.est_tokens == len(cz().render(c)) // 4


# ---------------------------------------------------------------- eval plan: a 60-minute session fits 16,000 tokens


def _worst_case_60_min():
    # 48 lines × 40 chars ≈ 1,920 chars of code, one line changed every minute for 60 minutes.
    # Each kept snapshot renders ≈ 2,000 chars ≈ 500 est. tokens per 2-minute tick ≈ 250 tokens/min,
    # the worst measured rate (253/min, session-format.md).
    base = [f"    line_{i:02d} = compute(nums, {i:02d})  # ......"[:39] for i in range(48)]
    snaps = []
    for m in range(61):
        lines = list(base)
        lines[m % 48] = f"    changed_{m:02d} = value + {m:02d}"[:39].ljust(39, ".")
        snaps.append(snap(at(m), "\n".join(lines)))
    return session(snaps, sid="sixty")


def test_a_60_minute_session_fits_the_16000_token_budget():
    c = cz().condense(_worst_case_60_min())
    assert c.duration_min == 60.0
    assert c.est_tokens <= 16_000
    assert not c.truncated, "a worst-rate 60-minute session fits without dropping code"
    assert c.est_tokens >= 12_000, "the hand-built session really is near the worst measured rate"


# ---------------------------------------------------------------- budget truncation (§5.4)


def _big_session():
    # Opened, 3 changed timed snapshots, a run on changed code, final. Each code ≈ 800 chars.
    def code(tag):
        return "\n".join(f"line {i} {tag} " + "x" * 30 for i in range(20))

    return session([snap(at(0), code("o")), snap(at(2), code("a")), snap(at(4), code("b")),
                    snap(at(6), code("c")), snap(at(7), code("r"))],
                   [run(at(7, 30)), submit(at(8))], sid="big")


def test_over_budget_drops_timed_code_earliest_first():
    full = cz().condense(_big_session())
    assert not full.truncated
    c = cz().condense(_big_session(), token_budget=full.est_tokens - 1)
    assert c.truncated and c.est_tokens <= full.est_tokens - 1
    timed = [m for m in c.moments if m.kind == "timed"]
    assert timed[0].code is None and timed[0].change is not None, "earliest timed code goes, its change stays"
    assert all(m.code is not None for m in timed[1:]), "only as many as needed are dropped"
    for m in c.moments:
        if m.kind in ("opened", "run"):
            assert m.code is not None, f"{m.kind} code is never dropped"


def test_over_budget_after_dropping_all_timed_code_raises():
    with pytest.raises(cz().CondenseBudgetError):
        cz().condense(_big_session(), token_budget=200)


# ---------------------------------------------------------------- pure (§5)


def test_condense_is_deterministic():
    a, b = cz().condense(S1), cz().condense(S1)
    assert a == b
    assert cz().render(a) == cz().render(b)
    assert cz().render(cz().condense(_big_session())) == cz().render(cz().condense(_big_session()))
