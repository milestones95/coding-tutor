"""07_condense_estimate.py

Why: the eval plan says the condensing token budget is set "after looking at real
sessions". This simulates the plan's rule (snapshot every 2 min if changed, plus one
at each run/submit; keep every run/submit) on the real capture data and reports raw
vs condensed size, so the budget is measured, not guessed. Read-only (immutable URI).
Token counts are estimated as chars/4 — an approximation, not a tokenizer count.

Run: python3 -I scripts/discovery/07_condense_estimate.py
"""
import difflib
import sqlite3
from datetime import datetime

DB = "file:data/reference/capture.db?immutable=1"
TICK_S = 120


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


con = sqlite3.connect(DB, uri=True)
rows = []
for sid, slug, start, last in con.execute(
    "SELECT id, slug, started_at, last_activity_at FROM sessions ORDER BY started_at"
):
    snaps = [(ts(t), c) for t, c in con.execute(
        "SELECT ts, code FROM snapshots WHERE session_id=? ORDER BY ts", (sid,))]
    evs = [(ts(t), k, st, e or "") for t, k, st, e in con.execute(
        "SELECT ts, kind, status, error_detail FROM judge_events WHERE session_id=? ORDER BY ts", (sid,))]
    if len(snaps) < 2:
        continue
    t0, t1 = ts(start), ts(last)
    raw = sum(len(c) for _, c in snaps) + sum(len(e) + len(st) for _, _, st, e in evs)

    def code_at(t):
        best = None
        for st_, c in snaps:
            if st_ <= t:
                best = c
        return best

    points = [t0 + k * TICK_S for k in range(1, int((t1 - t0) // TICK_S) + 1)]
    points += [t for t, *_ in evs] + [t1]
    kept, prev = [], None
    for t in sorted(points):
        c = code_at(t)
        if c is not None and c != prev:
            kept.append(c)
            prev = c
    full = sum(len(c) for c in kept)
    diffs = sum(
        len("".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), n=1)))
        for a, b in zip(kept, kept[1:])
    )
    ev_chars = sum(len(e) + len(st) + 40 for _, _, st, e in evs)
    first_plus_diffs = (len(kept[0]) if kept else 0) + diffs + len(kept[-1]) + ev_chars
    rows.append((slug[:28], round((t1 - t0) / 60, 1), len(snaps), raw // 4, len(kept),
                 (full + ev_chars) // 4, first_plus_diffs // 4))

print(f"{'slug':28} {'min':>5} {'snaps':>5} {'raw_tok':>7} {'kept':>4} {'full_tok':>8} {'diff_tok':>8}")
for r in rows:
    print(f"{r[0]:28} {r[1]:>5} {r[2]:>5} {r[3]:>7} {r[4]:>4} {r[5]:>8} {r[6]:>8}")
mins = sum(r[1] for r in rows)
print(f"\nfull-snapshot condensed tokens per active minute: {sum(r[5] for r in rows)/mins:.0f}")
print(f"first+diffs+final tokens per active minute:       {sum(r[6] for r in rows)/mins:.0f}")
print(f"raw tokens per active minute:                     {sum(r[3] for r in rows)/mins:.0f}")
