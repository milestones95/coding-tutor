"""11_verdict_worksheet.py

Why: submit capture is broken (0 submits stored, see 10_submit_timing.sql), so the human
backfills LeetCode verdicts by re-submitting each real session's final code by hand.
This writes (1) a worksheet with each session's exact final code, so the right code is
submitted (LeetCode's editor only holds the latest), and (2) a blank verdicts.csv the
human fills in. Both go to data/labels/ (gitignored: contains real code + eval labels).
Reads capture.db read-only. Never overwrites an existing verdicts.csv.

Run: python3 -I scripts/discovery/11_verdict_worksheet.py
"""
import csv
import os
import sqlite3
from datetime import datetime

DB = "file:data/reference/capture.db?immutable=1"
OUT = "data/labels"


def parse(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


con = sqlite3.connect(DB, uri=True)
sessions = con.execute(
    """SELECT s.id, s.slug, p.title, p.difficulty, s.started_at
       FROM sessions s JOIN problems p ON p.slug = s.slug
       WHERE s.end_reason = 'ended' ORDER BY s.started_at"""
).fetchall()

seen, md, rows = {}, ["# Verdict worksheet\n",
      "For each session: open the problem, paste the code below **exactly**, click "
      "**Submit**, and write the verdict in `verdicts.csv`.\n",
      "Verdict values: `Accepted`, `Wrong Answer`, `Time Limit Exceeded`, "
      "`Runtime Error`, `Memory Limit Exceeded`, `Compile Error`.\n"], []
for n, (sid, slug, title, diff, started) in enumerate(sessions, 1):
    seen[slug] = seen.get(slug, 0) + 1
    first, last = con.execute(
        """SELECT MIN(ts), MAX(ts) FROM (SELECT ts FROM snapshots WHERE session_id=?
           UNION ALL SELECT ts FROM judge_events WHERE session_id=?)""", (sid, sid)).fetchone()
    code = con.execute(
        "SELECT code FROM snapshots WHERE session_id=? ORDER BY ts DESC LIMIT 1", (sid,)
    ).fetchone()[0]
    runs = [r[0] for r in con.execute(
        "SELECT status FROM judge_events WHERE session_id=? ORDER BY ts", (sid,))]
    minutes = round((parse(last) - parse(first)).total_seconds() / 60, 1)
    local = parse(started).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    md += [f"\n## {n}. {title} ({diff}) — attempt #{seen[slug]}\n",
           f"- session_id: `{sid}`",
           f"- started: {local} · time (first→last event): {minutes} min",
           f"- runs: {' → '.join(runs) if runs else '(none)'}\n",
           "```python", code.rstrip(), "```"]
    rows.append({"n": n, "session_id": sid, "slug": slug, "attempt": seen[slug],
                 "minutes": minutes, "last_run": runs[-1] if runs else "",
                 "verdict": "", "tests_passed": "", "tests_total": "", "note": ""})

os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/verdict_worksheet.md", "w") as f:
    f.write("\n".join(md) + "\n")
csv_path = f"{OUT}/verdicts.csv"
if os.path.exists(csv_path):
    print(f"{csv_path} exists — left untouched")
else:
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
for r in rows:
    print(f"{r['n']}. {r['slug']} #{r['attempt']}  {r['minutes']} min  last run: {r['last_run'] or '-'}")
