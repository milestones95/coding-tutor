"""The condenser: Session → CondensedSession → text (architecture §5, D-006, D-013, D-034).

Every LLM field reads this, and only this, view of a session (rule 3). It is pure: no I/O, no
clock, no randomness, so the same session always renders byte-identically. Any change to the
rules below bumps CONDENSER_VERSION, because stored timelines are stamped with it (D-012).

How `condense` works, in one pass:
1. Collect candidates: the opened snapshot, every 2-minute tick up to t_end, every run and
   submit, and FINAL. Each one is paired with the snapshot it would show: the latest one at or
   before its time.
2. Sort them once by (time, kind rank): ties go opened < timed < run < submit < final.
3. Walk them in order, remembering the last code shown. A tick whose code didn't change is
   skipped; a run, submit or final on unchanged code points back with `code_ref`; anything
   with new code gets a change summary against the last code shown.
4. Backfilled submits (time not captured) go after FINAL.
5. If the render is over the token budget, drop timed code, earliest first.
"""

import bisect
import difflib
from datetime import datetime, timedelta
from typing import Literal

from tutor.models import ChangeSummary, CondensedSession, Moment, RunEvent, Session, Snapshot, SubmitEvent

CONDENSER_VERSION = "c1"
REWRITE_AT = 0.5
Kind = Literal["opened", "timed", "run", "submit", "final"]
_RANK: dict[Kind, int] = {"opened": 0, "timed": 1, "run": 2, "submit": 3, "final": 4}


class CondenseBudgetError(Exception):
    """Still over the token budget after every timed Moment's code was dropped."""


# ---------------------------------------------------------------- time (§5.1)


def session_times(session: Session) -> tuple[datetime, datetime]:
    """(t0, t_end). t0: the earliest snapshot or event. t_end: the last captured submit, else
    the last snapshot or event. Time to finish uses this too, so the two can't drift (§5.1)."""
    stamps = [s.ts for s in session.snapshots] + [e.ts for e in session.events if e.ts is not None]
    submits = [e.ts for e in session.events if isinstance(e, SubmitEvent) and e.ts is not None]
    return min(stamps), max(submits) if submits else max(stamps)


def elapsed_min(ts: datetime, t0: datetime) -> float:
    return round((ts - t0).total_seconds() / 60, 1)


# ---------------------------------------------------------------- change summary (§5.3)


def change_summary(prev: str, new: str) -> ChangeSummary:
    m = difflib.SequenceMatcher(None, prev.splitlines(), new.splitlines(), autojunk=False)
    added = removed = 0
    for op, i1, i2, j1, j2 in m.get_opcodes():
        if op in ("replace", "insert"):
            added += j2 - j1
        if op in ("replace", "delete"):
            removed += i2 - i1
    fraction = round(1 - m.ratio(), 2)
    return ChangeSummary(lines_added=added, lines_removed=removed, changed_fraction=fraction,
                         rewrite=fraction >= REWRITE_AT)


# ---------------------------------------------------------------- condense (§5.2, §5.4)


def _snapshot_at(snapshots: list[Snapshot], times: list[datetime], t: datetime) -> Snapshot | None:
    i = bisect.bisect_right(times, t)
    return snapshots[i - 1] if i else None


def _cut(event, error_max_chars: int):
    """The event with its error text cut to error_max_chars, so render needs no settings."""
    err = event.error_detail
    if err is not None and len(err) > error_max_chars:
        return event.model_copy(update={"error_detail": err[:error_max_chars] + "… [truncated]"})
    return event


def condense(session: Session, *, interval_s: int = 120, error_max_chars: int = 500,
             token_budget: int = 16_000) -> CondensedSession:
    snaps = sorted(session.snapshots, key=lambda s: s.ts)
    times = [s.ts for s in snaps]
    t0, t_end = session_times(session)
    latest = max([s.ts for s in snaps] + [e.ts for e in session.events if e.ts is not None])

    # 1. candidates: (ts, rank, kind, snapshot shown, event)
    candidates: list[tuple[datetime, int, Kind, Snapshot | None, RunEvent | SubmitEvent | None]] = [
        (snaps[0].ts, _RANK["opened"], "opened", snaps[0], None)]
    k = 1
    while (tick := t0 + timedelta(seconds=k * interval_s)) <= t_end:
        candidates.append((tick, _RANK["timed"], "timed", _snapshot_at(snaps, times, tick), None))
        k += 1
    for e in session.events:
        if e.ts is not None:
            candidates.append((e.ts, _RANK[e.kind], e.kind, _snapshot_at(snaps, times, e.ts), e))
    candidates.append((latest, _RANK["final"], "final", snaps[-1], None))

    # 2–3. one ordered walk
    moments: list[Moment] = []
    last_code: str | None = None
    last_idx: int | None = None
    for ts, _, kind, snap, event in sorted(candidates, key=lambda c: (c[0], c[1])):
        code = snap.code if snap is not None else None
        if kind == "timed" and (code is None or code == last_code):
            continue  # nothing new at this tick
        shown, ref, change = code, None, None
        if code is None:
            shown = None  # an event before the first snapshot: no code to show
        elif code == last_code and kind != "opened":
            shown, ref = None, last_idx
        elif kind != "opened":
            change = change_summary(last_code or "", code)
        lag = None
        if event is not None and snap is not None and event.ts is not None:
            lag = round((event.ts - snap.ts).total_seconds(), 1)
        moments.append(Moment(
            elapsed_min=elapsed_min(ts, t0), ts=ts, kind=kind, code=shown, code_ref=ref, change=change,
            run=_cut(event, error_max_chars) if isinstance(event, RunEvent) else None,
            submit=_cut(event, error_max_chars) if isinstance(event, SubmitEvent) else None,
            snapshot_lag_s=lag))
        if shown is not None:
            last_code, last_idx = shown, len(moments) - 1

    # 4. backfilled submits: after FINAL, taken to have submitted the final code
    final = moments[-1]
    final_ref = len(moments) - 1 if final.code is not None else final.code_ref
    for e in session.events:
        if isinstance(e, SubmitEvent) and e.ts is None:
            moments.append(Moment(elapsed_min=final.elapsed_min, ts=None, kind="submit", code=None,
                                  code_ref=final_ref, change=None, submit=_cut(e, error_max_chars)))

    # 5. token budget
    def build(ms: list[Moment], truncated: bool) -> CondensedSession:
        c = CondensedSession(session_id=session.session_id, condenser_version=CONDENSER_VERSION,
                             problem=session.problem, language=snaps[-1].language,
                             duration_min=elapsed_min(t_end, t0), moments=ms, truncated=truncated, est_tokens=0)
        return c.model_copy(update={"est_tokens": len(render(c)) // 4})

    c = build(moments, False)
    while c.est_tokens > token_budget:
        i = next((i for i, m in enumerate(moments) if m.kind == "timed" and m.code is not None), None)
        if i is None:
            raise CondenseBudgetError(
                f"session {session.session_id}: {c.est_tokens} est. tokens after dropping all timed code "
                f"(budget {token_budget})")
        moments[i] = moments[i].model_copy(update={"code": None})
        c = build(moments, True)
    return c


# ---------------------------------------------------------------- render (§5.5)


def _change_text(ch: ChangeSummary | None) -> str:
    if ch is None:
        return ""
    text = f" · +{ch.lines_added} −{ch.lines_removed} lines · {round(ch.changed_fraction * 100)}% changed"
    return text + (" · REWRITE" if ch.rewrite else "")


def _header(m: Moment) -> str:
    at = f"[{m.elapsed_min:.1f} min] "
    lag = f" · code as of {m.snapshot_lag_s:.1f} s earlier" if m.snapshot_lag_s else ""
    if m.kind == "opened":
        return at + "CODE WHEN THE PAGE OPENED"
    if m.kind == "timed":
        return at + "SNAPSHOT" + _change_text(m.change)
    if m.kind == "run" and m.run is not None:
        counts = f" · {m.run.tests_passed}/{m.run.tests_total} passed" if m.run.tests_total is not None else ""
        return at + f"RUN · {m.run.status}" + counts + lag + _change_text(m.change)
    if m.kind == "submit" and m.submit is not None:
        s = m.submit
        counts = f" · {s.tests_passed}/{s.tests_total} tests passed" if s.tests_total is not None else ""
        if s.ts is None:
            return f"SUBMIT (time not captured) · {s.verdict}" + counts
        return at + f"SUBMIT · {s.verdict}" + counts + lag + _change_text(m.change)
    return at + "FINAL CODE" + _change_text(m.change)


def render(c: CondensedSession) -> str:
    """The plain text every prompt receives (§5.5). Depends only on `c`, never on settings."""
    p = c.problem
    runs = sum(m.kind == "run" for m in c.moments)
    submits = sum(m.kind == "submit" and m.submit is not None and m.submit.source == "capture_submit"
                  for m in c.moments)
    out = [f"Problem: {p.title} ({p.difficulty}) · tags: {', '.join(p.tags)}",
           f"Session: {c.duration_min:.1f} min · {runs} runs · {submits} submits"]
    for m in c.moments:
        out.append("")
        out.append(_header(m))
        event = m.run or m.submit
        if event is not None and event.error_detail:
            out.append(event.error_detail)
        if m.code is not None:
            out.append(f"```{c.language}\n{m.code}\n```")
        elif m.code_ref is not None:
            if m.submit is None or m.submit.ts is not None:  # the backfilled line already says final code
                out.append(f"(code unchanged since {c.moments[m.code_ref].elapsed_min:.1f} min)")
        elif m.kind == "timed":
            out.append("(code omitted to fit the token budget)")
        else:
            out.append("(no code captured yet)")
    return "\n".join(out) + "\n"
