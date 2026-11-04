"""Why: the eval plan (2026-11-03) adds stuck periods to the condensing step, flagged by rule:
(A) 3+ failing runs in a row with the same error, or (B) 3+ snapshots in a row (6+ minutes)
with under ~5 lines changed and no passing run. "Tune the thresholds on real sessions."
This measures what each candidate rule would flag on the real sessions, before the rule is
designed. Read-only: the frozen copy is opened immutable=1, the live DB mode=ro.

    uv run python scripts/discovery/18_stuck_periods.py            # frozen copy
    uv run python scripts/discovery/18_stuck_periods.py --live     # live capture DB too

Rule B is measured on the 2-minute tick grid the condenser already uses (architecture §5.2),
because raw snapshots are change-triggered every ~5 s: "3 snapshots in a row" only means
6 minutes on the grid. Lines changed per tick = lines added + removed between the code at
consecutive ticks (difflib, as §5.3), summed over the window, so typing then deleting counts
as activity, not as being stuck.
"""

import difflib
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PASSING = {"Passed sample tests", "Accepted"}


def ts(t: str) -> float:
    return datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp()


def changed(a: str, b: str) -> int:
    m = difflib.SequenceMatcher(None, a.splitlines(), b.splitlines(), autojunk=False)
    return sum((i2 - i1) + (j2 - j1) for op, i1, i2, j1, j2 in m.get_opcodes() if op != "equal")


def run_streaks(runs, key):
    """Maximal streaks of consecutive failing runs that share key(run); returns (len, start, end)."""
    out, cur = [], []
    for r in runs + [None]:
        if r is not None and r["status"] not in PASSING and (not cur or key(r) == key(cur[-1])):
            cur.append(r)
            continue
        if len(cur) >= 3:
            out.append((len(cur), cur[0]["m"], cur[-1]["m"]))
        cur = [r] if r is not None and r["status"] not in PASSING else []
    return out


def stalls(snaps, runs, t0, t_end, interval=120, ticks_needed=3, max_lines=5, net=False):
    """Windows of >= ticks_needed consecutive tick intervals with < max_lines changed in total
    and no passing run inside; overlapping windows merged. Returns [(start_min, end_min, lines)]."""
    grid = [t0 + k * interval for k in range(int((t_end - t0) // interval) + 1)]
    if grid[-1] < t_end:
        grid.append(t_end)

    def code_at(t):
        best = None
        for s in snaps:
            if s["t"] <= t:
                best = s["code"]
        return best or ""

    codes = [code_at(t) for t in grid]
    per = [changed(codes[i], codes[i + 1]) for i in range(len(grid) - 1)]
    if net:  # variant: net change start->end of the window, so churn that goes nowhere counts as stuck
        return _net_stalls(grid, codes, runs, t0, ticks_needed, max_lines)
    passing = [r["t"] for r in runs if r["status"] in PASSING]
    periods = []
    for i in range(len(per) - ticks_needed + 1):
        j = i + ticks_needed
        lo, hi = grid[i], grid[j]
        if sum(per[i:j]) < max_lines and not any(lo <= p <= hi for p in passing):
            if periods and lo <= periods[-1][1]:
                periods[-1] = (periods[-1][0], hi, periods[-1][2] + per[j - 1])
            else:
                periods.append((lo, hi, sum(per[i:j])))
    return [(round((a - t0) / 60, 1), round((b - t0) / 60, 1), n) for a, b, n in periods]


def _net_stalls(grid, codes, runs, t0, ticks_needed, max_lines):
    passing = [r["t"] for r in runs if r["status"] in PASSING]
    periods = []
    for i in range(len(grid) - ticks_needed):
        j = i + ticks_needed
        lo, hi = grid[i], grid[j]
        n = changed(codes[i], codes[j])
        if n < max_lines and not any(lo <= p <= hi for p in passing):
            if periods and lo <= periods[-1][1]:
                periods[-1] = (periods[-1][0], hi, n)
            else:
                periods.append((lo, hi, n))
    return [(round((a - t0) / 60, 1), round((b - t0) / 60, 1), n) for a, b, n in periods]


def sessions(db_uri):
    con = sqlite3.connect(db_uri, uri=True)
    rows = con.execute("SELECT id, slug FROM sessions ORDER BY started_at").fetchall()
    for sid, slug in rows:
        snaps = [{"t": ts(t), "code": c} for t, c in
                 con.execute("SELECT ts, code FROM snapshots WHERE session_id=? ORDER BY ts", (sid,))]
        judge = [{"t": ts(t), "kind": k, "status": s, "err": e or ""} for t, k, s, e in
                 con.execute("SELECT ts, kind, status, error_detail FROM judge_events WHERE session_id=? ORDER BY ts", (sid,))]
        if len(snaps) <= 1 and not judge:
            continue  # non-attempt (architecture §4.4)
        yield sid, slug, snaps, judge
    con.close()


def first_line(e):
    return e.strip().splitlines()[0] if e.strip() else ""


def report(label, db_uri):
    print(f"\n=== {label} ===")
    for sid, slug, snaps, judge in sessions(db_uri):
        t0 = min([s["t"] for s in snaps] + [j["t"] for j in judge])
        subs = [j["t"] for j in judge if j["kind"] == "submit"]
        t_end = max(subs) if subs else max([s["t"] for s in snaps] + [j["t"] for j in judge])
        for j in judge:
            j["m"] = round((j["t"] - t0) / 60, 1)
        runs = judge  # runs and submits, in order; both are "failing runs" when they fail
        fails = [f"{j['m']}:{j['status'][:12]}" for j in runs if j["status"] not in PASSING]
        print(f"\n{slug} {sid[:8]}  {round((t_end - t0) / 60, 1)} min, {len(snaps)} snaps, "
              f"{len(runs)} runs/submits, failing: {fails}")
        for name, key in [("status", lambda r: r["status"]),
                          ("status+1st line", lambda r: (r["status"], first_line(r["err"]))),
                          ("status+full error", lambda r: (r["status"], r["err"]))]:
            print(f"  A same-error streaks by {name:18s}: {run_streaks(runs, key)}")
        for ticks, lines in [(3, 5), (3, 3), (3, 10), (4, 5)]:
            print(f"  B stall ticks>={ticks} lines<{lines:<3}: {stalls(snaps, runs, t0, t_end, ticks_needed=ticks, max_lines=lines)}")
        for ticks, lines in [(3, 5), (3, 10)]:
            print(f"  B-net   ticks>={ticks} lines<{lines:<3}: {stalls(snaps, runs, t0, t_end, ticks_needed=ticks, max_lines=lines, net=True)}")


if __name__ == "__main__":
    report("frozen copy (data/reference/capture.db)", f"file:{REPO / 'data/reference/capture.db'}?mode=ro&immutable=1")
    if "--live" in sys.argv:
        report("live (data/capture.db)", f"file:{REPO / 'data/capture.db'}?mode=ro")
