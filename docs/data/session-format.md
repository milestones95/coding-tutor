# Session Format — what the capture tool actually records

Measured 2026-10-31 against `data/reference/capture.db` (opened read-only, `immutable=1`).
Every number below comes from a query in `scripts/discovery/` (file named next to it).

---

## Most surprising finding: there is no LeetCode verdict in the data

**Zero submits have been captured.** All 24 `judge_events` rows are `kind = 'run'`
(sample tests only). No session has `end_reason = 'accepted'`. (`03`, `04`, `08`)

The eval plan's status grader is "exact match vs. LeetCode verdict", and the plan calls the
verdict "free ground-truth labels". As captured, there are **0 verdict labels**.

**Update 2026-11-02:** the human reports submitting most of these sessions, and they
passed. Nothing is recorded after the last Run in any session (`10`), and all 24
`submission_id`s start with `runcode_` — the Run endpoint. The likely cause is that the
extension captures Run results and never Submit results. This is inferred, not confirmed
against the extension's code. `end_reason = 'ended'` comes from the "End session"
button, and has nothing to do with the missing submits.

**Workaround (D-005):** the human re-submits each real session's final code and records the
verdict in `data/labels/verdicts.csv`. `scripts/discovery/11_verdict_worksheet.py` generates
the worksheet with exact final code per session. The schema *can* hold a submit, so
fixing the extension is a separate scope item.

Proposed eval-plan change → see [Conflicts with the eval plan](#conflicts-with-the-eval-plan), C1.

## Second finding: the verdict is not separable as stored

> **Superseded 2026-11-02 by D-014.** The verdict is now a fact that models and the agent
> may read, so separating it is no longer required. Kept for the record.

When submits do get captured, the verdict will sit in **the same table and same columns as
run results** — `judge_events.status`, distinguished only by `kind`. The eval plan says the
condensed events include "every run and submit with its result and error message". A
submit's result *is* the verdict. Followed literally, the condensing step would put the
label straight into every LLM prompt, breaking rule 1.

The verdict also leaks through two other places:

- `sessions.end_reason = 'accepted'` encodes a passing submit.
- The `attempts` / `attempt_gaps` tables are **output of an earlier LLM analyzer built into
  the capture extension** (`source = 'extension'`, `confidence`, `verdict_reason`,
  `approach_pattern`). `attempts.status` (`passed | failed | gave_up`) is a model's
  prediction, not a LeetCode verdict. It must be neither a model input nor an eval label.

## Third finding: repeat sessions start with the previous session's code

LeetCode restores saved editor code when a problem is reopened. In 6 of 7 repeat sessions,
the first snapshot is byte-identical to the previous same-slug session's final snapshot
(`09`). The second `two-sum` attempt (`70241a81`) opens with a complete solution and passes
its run at 2.4 min. A model reading that timeline would credit a 2-minute solve that was
really a re-run of old code. Time to finish and "approaches tried" are both distorted.

---

## Schema (confirmed, `01`)

| Table | Rows | What it is | Belongs to |
|---|---:|---|---|
| `problems` | 4,091 | LeetCode problem catalog | capture metadata |
| `sessions` | 22 | One row per opened problem page | capture |
| `snapshots` | 646 | Full editor text, change-triggered | capture |
| `judge_events` | 24 | Run / submit results | capture (**holds verdict on submit rows**) |
| `attempts` | 9 | Extension's own LLM analysis, 1 per analyzed session | **prior analyzer output — not capture, not labels** |
| `attempt_gaps` | 15 | Extension's LLM-found weaknesses per attempt | **prior analyzer output** |

```
sessions(id TEXT PK /*uuid4*/, slug, started_at, last_activity_at, ended_at,
         end_reason /*accepted|ended|gave_up|idle*/, analysis_status, analysis_error)
snapshots(id INT PK, session_id FK, ts, language, code /*full editor text*/, partial INT)
judge_events(id INT PK, session_id FK, ts, kind /*run|submit*/, status, tests_passed,
             tests_total, runtime, memory, error_detail, language, submission_id)
problems(slug PK, frontend_id, title, difficulty, tags /*JSON array*/, category,
         description, paid_only, ac_rate, updated_at)
```

- **Keying.** Sessions are keyed by a UUID string. All child rows join on `session_id`.
- **Timestamps.** ISO-8601 UTC with milliseconds and `Z` (`2026-10-28T20:00:00.122Z`).
  `attempts.date` is local date; one session started `2026-10-28T00:55Z` is dated
  `2026-10-27`, so local time is behind UTC. "Attempted at" must pick a timezone explicitly.
- **Language.** 646/646 snapshots and 24/24 judge events are `python3`.
- **`partial`.** 0 of 646 snapshots came from the DOM fallback.

## Event shape

**Code is captured as full-text snapshots on change, not per keystroke and not on a
timer.** (`04`)

| Gap between consecutive snapshots | Count |
|---|---:|
| < 2 s | 0 |
| 2–10 s | 515 |
| 10–60 s | 96 |
| > 60 s | 14 |
| min / mean / max | 4.9 s / 9.7 s / 225 s |
| consecutive snapshots with identical code | **0** |

So the tool debounces at ~5 s and only writes when the code changed. Each row is the whole
file, not a diff.

Illustrative excerpt (first lines of one snapshot):

```python
class Solution:
    def twoSum(self, nums: list[int], target: int) -> list[int]:
        # use hashmap with the numbers and their indexes
```

**Runs do not store the code they ran.** The nearest earlier snapshot is 0.0–27.3 s before
each run (`06`). With a ~5 s debounce and no identical consecutive snapshots, the last
snapshot before a run is the best available stand-in for "code at run". The condenser should
use it and say so.

## Runs and submits (`04`)

| kind | status | n | error_detail | tests_passed/total |
|---|---|---:|---|---|
| run | Passed sample tests | 8 | — | filled |
| run | Wrong Answer (sample tests) | 12 | `Output: … \| Expected: …` | filled |
| run | Runtime Error | 3 | Python exception + caret line | filled (0/n) |
| run | Time Limit Exceeded | 1 | empty | **null** |
| submit | — | **0** | — | — |

Runs and submits are distinguishable by `kind`. Result and error text are stored. Run
status strings differ from submit strings (`Wrong Answer (sample tests)` vs. LeetCode's
`Wrong Answer`), but that is the only signal; do not rely on string shape to separate them.

## Problem metadata (`05`)

All 15 session slugs have title, difficulty, and tags in `problems`. Descriptions exist for
exactly 15 of 4,091 problems — the ones that were opened — so every captured session has its
description. **No external lookup is needed.**

`problems.category` is a NeetCode-style bucket (`Arrays & Hashing`, `1-D DP`, …). It is not
the eval plan's algorithm-label list and must not be mistaken for it. Tags are LeetCode tag
slugs, which are problem-level hints, not the approach the user took.

## Sizes (`03`, `07`)

Only the 9 sessions with `end_reason = 'ended'` are real practice. The other 13 are
`idle` page opens: 0–1 snapshots, ≤ 0.1 min, no runs.

| Session (slug) | Active min | Snapshots | Raw tokens* | Kept snapshots (plan rule) | Condensed, full text* | Condensed, diffs* |
|---|---:|---:|---:|---:|---:|---:|
| two-sum | 4.2 | 27 | 2,633 | 4 | 621 | 443 |
| merge-sorted-array | 16.7 | 109 | 21,115 | 12 | 3,110 | 1,438 |
| sort-colors | 24.4 | 122 | 27,556 | 16 | 4,586 | 1,675 |
| sort-colors | 7.2 | 53 | 7,840 | 5 | 1,027 | 759 |
| remove-duplicates… | 12.4 | 81 | 11,380 | 7 | 1,124 | 793 |
| design-browser-history | 22.4 | 147 | 52,565 | 14 | 5,664 | 2,412 |
| coin-change | 12.1 | 70 | 11,760 | 10 | 2,539 | 1,226 |
| two-sum | 2.4 | 24 | 1,808 | 2 | 237 | 283 |

\* chars ÷ 4, an estimate, not a tokenizer count. "Diffs" = first snapshot + unified diffs
between kept snapshots + final code + run results. `search-insert-position` (1 snapshot)
omitted.

| Measure | min | median | max |
|---|---:|---:|---:|
| Active minutes (real sessions) | 0.1 | 12.4 | 24.4 |
| Snapshots per real session | 1 | 70 | 147 |
| Raw code bytes per real session | 89 | 45,502 | 209,662 |

Per active minute: raw ≈ **1,342 tokens**, condensed full text ≈ **186**, condensed diffs
≈ **89**. Worst session (design-browser-history) is 253 tokens/min full text.

**Token budget implication.** No real session is longer than 24.4 min, so the plan's
60-minute budget is an extrapolation: ≈ 11k tokens full-text at the average rate, ≈ 15k
at the worst observed rate, ≈ 5–6k in diff form. Raw events for 60 min would be ≈ 80k.
Condensing is clearly needed; the plan's rule (every 2 min, plus runs) already gets a 7×
reduction. The plan's "50 minutes ≈ 25 timed snapshots" holds.

## Coverage for the 30-case dataset

> **Updated 2026-11-02 with hand-backfilled verdicts (D-005, `data/labels/verdicts.csv`).**
> 8 usable real sessions: **7 Accepted, 1 Wrong Answer** (sort-colors #1, 59/90 tests,
> human-confirmed). search-insert-position is excluded — the human confirms the
> page was opened but the problem was never attempted. The table below was measured
> before backfill and is superseded by these counts.
>
> - **Real data is skewed to Passed** (7 of 8). Every failing status the dataset needs —
>   wrong answer beyond this one case, too slow, runtime error, near-misses — must come
>   from synthetic cases or new sessions. Roughly 22 of 30 cases are synthetic.
> - **coin-change is Accepted (191/191)**, yet the extension's analyzer labeled it
>   `failed`. That is a real false-negative from a model judging status, which makes it a
>   good hard case for the status eval.
> - **"Passed sample tests" agreed with the verdict 7 of 7 times** here. Too few cases to
>   say Run results predict Submit, and a model leaning on that shortcut would miss TLEs.

| Eval-plan status | Real sessions with a LeetCode verdict | Real sessions that could be hand-labeled |
|---|---:|---|
| Passed | 0 | ~5 whose last run passed samples (not proof of passing) |
| Failed – wrong answer | 0 | sort-colors #1 (last run WA) |
| Failed – too slow | 0 | none (one TLE run, mid-session, later fixed) |
| Failed – runtime error | 0 | none at session end |
| Not submitted | **all 9** | all 9 |

Failure-type coverage from real sessions, by inspection of run results only (needs human
labels): implementation bug (sort-colors #1, coin-change runs), didn't finish
(search-insert-position stub). No real case of *too slow (complexity)* as an outcome. No
near-miss submit.

**Gaps that must be filled synthetically or by new captures:** every submit verdict; all of
`Failed – too slow`, `Failed – runtime error` at submit; near-misses; any session > 25 min;
algorithm coverage beyond hash map, two pointers, binary search, stack, linked list, DP
(no graphs, trees, heaps, intervals, tries, union find, BFS/DFS). Real data can supply at
most ~9 of 30 cases, all "not submitted".

## Quality (`03`, `06`, `09`)

- **Idle sessions.** 13 of 22 sessions are page opens with nothing done. A 14th,
  search-insert-position (`63b86d7c`), has `end_reason = 'ended'` because the End session
  button was clicked, but the problem was never attempted (human-confirmed). So
  `end_reason` alone cannot be the exclusion rule. A rule that matches all 14 and none of
  the 8 real sessions: **exclude sessions with ≤ 1 snapshot and no judge events** (the
  code never changed). Without it, Part 2 would count a page visit as a failed attempt —
  the extension's analyzer already did exactly that (`attempts.status = 'failed'`).
- **No submits at all** — see top.
- **Code carry-over** between repeat sessions — see top.
- **Split sessions.** `search-insert-position` has sessions 5.6 min apart, consistent with a
  reload creating a new session. Sort-colors attempts 78 min apart look like genuine retries.
  There is no field linking a reloaded session to its predecessor.
- **TLE runs** have null `tests_passed` / `tests_total` and empty `error_detail`.
- **No missing timestamps.** `ended_at` is never null; `partial` is never set.
- **`ended_at` vs `last_activity_at`.** `ended_at` lags last activity by up to ~1 min (time
  to close the tab); "time to finish" should use the last event, not `ended_at`.

## Conflicts with the eval plan

- **C1 — Status labels don't exist.** Plan: status graded against the LeetCode verdict. Data:
  0 verdicts. *Proposed change:* (a) verify submit capture with one deliberate submit
  (pass, WA, TLE) before Part 1 status work; (b) state in the plan that status labels for
  real sessions come from new submits, and the rest are synthetic with a human-written
  label; (c) decide how "Not submitted" is graded (already an open question in the plan).
- **C2 — "Every run and submit with its result" would leak the verdict.** *Proposed
  change:* condensed events keep **run** results in full; a **submit** appears as an event
  with its timestamp only, and its result is dropped by the condenser. The verdict is read
  from submit rows only by the label loader.
- **C3 — Repeat sessions inherit old code.** *Resolved by D-006.* (Original proposal: the condenser marks a first
  snapshot that equals the previous same-slug session's final code as "carried over", and
  time to finish starts at the first *change* after that — rejected: detection misses
  coin-change, which carries code from before capture existed.)
- **C4 — Token budget set from ≤ 25-minute sessions.** Real sessions are shorter than the
  plan's 60-minute test case. *Proposed change:* set the budget from the measured worst
  rate (≈ 253 tok/min → 15k for 60 min, full text) and build the 60-minute unit test from
  a hand-built event stream.
- **C5 — The extension already runs its own analyzer.** `attempts` duplicates several Part 1
  fields (status, time taken, category, approach). It must not feed the model, the labels,
  or Part 2. Decide whether the new analysis DB is separate (recommended) or whether these
  tables are retired.

## Open questions

1. Does submit capture work? Needs one real submit per verdict type to confirm.
2. Which timezone is "attempted at"? (Local date is behind UTC.)
3. How are reload-split sessions merged, if at all?
4. Is `idle` + < 2 snapshots the right exclusion rule?
5. What does the extension write to `sessions.analysis_status` going forward, and does its
   analyzer keep writing to `attempts` in the same file we read from?
