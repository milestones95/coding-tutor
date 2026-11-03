# Decisions

Append-only. Each entry records a decision a future you might otherwise reverse without
knowing why — with the reason or the measurement behind it, not just the conclusion.

To change a decision, add a new entry that supersedes the old one by number. Never edit
or delete an old entry.

**Format**

```
## D-NNN · <short title> · YYYY-MM-DD · <who: human / architect / build / test / pm>
**Decision.** What was decided.
**Why.** The reason or measurement. A number cites its versions.
**Rejected.** The alternative, and why not.
**Supersedes.** D-NNN, or nothing.
```

---

## D-001 · The Progress Agent gets one raw-SQL tool · 2026-10-31 · human
**Decision.** Part 2 exposes a single read-only `run_sql` tool, with the schema in the
system prompt.
**Why.** It's the most flexible option, and it teaches query errors and recovery, which
the trajectory evals are meant to measure.
**Rejected.** A set of fixed tools (e.g. `get_topic_stats`). Safer, but the agent would
rarely fail in interesting ways, so there'd be less to learn from.
**Supersedes.** —

## D-002 · Status is judged by the model, not taken from LeetCode · 2026-10-31 · human
**Decision.** The LLM predicts pass/fail status from the final code. The LeetCode verdict
is saved at capture time as the eval label only and never reaches the model.
**Why.** That makes status an eval exercise — can a model read code and predict whether it
passes — with free ground-truth labels.
**Rejected.** Using the verdict directly. Accurate, but nothing to evaluate.
**Supersedes.** —

## D-003 · Part 2 is evaluated on a fixture database, not on Part 1's output · 2026-10-31 · human
**Decision.** The Progress Agent is tested against about 50 fake sessions with planted
patterns.
**Why.** The right answers are known, so any mistake is the agent's, not a Part 1
labeling error.
**Rejected.** Evaluating on real Part 1 output. Mixes two sources of error.
**Supersedes.** —

## D-004 · The builder never writes what judges it · 2026-10-31 · human
**Decision.** `/test write` owns contract and acceptance tests, datasets, graders, the
fixture and judge prompts. The builder writes only `tests/unit/`. Labels and hand grades
are confirmed by the human.
**Why.** A builder that writes its own labels or expected answers can make them match its
output without noticing, and the eval stops meaning anything.
**Rejected.** Builder writes all tests in the same session — faster, but self-grading.
**Supersedes.** —

## D-005 · Backfill LeetCode verdicts by hand-resubmitting final code · 2026-11-02 · human
**Decision.** For the 9 real captured sessions, the human re-submits each session's final
snapshot on LeetCode and records the verdict in `data/labels/verdicts.csv` (gitignored).
That file is the verdict source for these sessions; it is an eval label under rule 1 and
lives apart from the capture DB and from anything the inference path reads.
**Why.** 0 of 24 captured judge events are submits, and all 24 IDs are `runcode_` (Run
endpoint), though the human reports submitting most sessions — submit capture appears
broken (`scripts/discovery/10_submit_timing.sql`). Waiting on an extension fix would block
Part 1 status work. Re-submitting the same code against the same hidden tests should give
the same verdict.
**Rejected.** (a) Using the last Run result as the label — sample tests only; would mislabel
near-misses as Passed. (b) Using the extension's `attempts.status` — a model's prediction,
not ground truth. (c) Blocking until submit capture is fixed.
**Caveat.** Verdicts are from re-submission on 2026-11-02, not the original attempt; if
LeetCode changed a problem's tests since, the label could differ from what happened then.
Future sessions still need submit capture fixed (separate `/pm idea`).
**Supersedes.** —

## D-006 · Carried-over code is shown, not detected · 2026-11-02 · human
**Decision.** The condenser always labels a session's first snapshot as "code when the page
opened". Time to finish stays first event → last event, as the eval plan defines it. Whether
a session started from earlier code is a fact the human records at labeling time, not
something code infers. No `carried_over` field for now; adding one goes through `/pm idea`.
**Why.** 2 of 8 real sessions open with prior code (two-sum #2: previous session's final;
coin-change: 79 lines from before capture existed). Matching against the previous same-slug
session catches only the first, and LeetCode starter templates aren't stored, so detection
would be wrong half the time (`scripts/discovery/09_carryover.sql`, `12_first_snapshot.sql`).
**Rejected.** (a) Subtracting carried-over time — depends on unreliable detection.
(b) Excluding those sessions — loses 2 of 8 real cases, including coin-change, a known
model false-"failed".
**Supersedes.** —

## D-007 · Stack: Python 3.13, uv, pytest, pydantic, stdlib sqlite3 · 2026-11-02 · human
**Decision.** All application code, eval runners and graders are Python 3.13, with
dependencies managed by uv, tests in pytest, data models and LLM-output validation in
pydantic, and SQLite through the stdlib `sqlite3` module (no ORM).
**Why.** Already installed; the discovery scripts are Python; one language across the
analyzer, agent and evals.
**Rejected.** TypeScript/Node — workable, but a second language for no gain. An ORM —
hides the SQL that Part 2's `run_sql` agent writes against the same schema.
**Supersedes.** —

## D-008 · One client wrapper, hand-written adapters for Claude, OpenAI and Gemini · 2026-11-02 · human
**Decision.** The single LLM client wrapper (rule 5) exposes one call. Each provider has a
thin adapter over its own official SDK. Model and provider are config. Per-model prices
live in a config table, so cost is computed the same way for every provider. Claude's
adapter is built first; OpenAI and Gemini adapters arrive with build step 7 (model
comparison).
**Why.** The eval plan's model comparison spans providers. Writing the adapters directly
keeps structured-output handling, token counting and pricing visible and testable — those
differences are part of what the comparison measures.
**Rejected.** LiteLLM or a similar router — less code, but it hides per-provider
behavior and becomes the source of truth for cost numbers. Building all three adapters up
front — slows Parts 1 and 2 for a step that comes last.
**Supersedes.** —

## D-009 · The Part 2 agent loop is hand-written · 2026-11-02 · human
**Decision.** The Progress Agent loop is plain Python: call model, run tool, append result,
repeat up to the step cap, log every step. No agent framework.
**Why.** The project exists to learn the loop, and the trajectory evals must see every
step, error and retry.
**Rejected.** Claude Agent SDK / SDK tool runners — hide the loop and are provider-specific,
which would also break the cross-provider comparison (D-008).
**Supersedes.** —

## D-010 · No MCP server for now · 2026-11-02 · human
**Decision.** `run_sql` is a Python function called by the harness. No MCP adapter.
**Why.** The eval plan doesn't require MCP. Fewer moving parts.
**Rejected.** A thin MCP adapter now — useful for querying history from Claude Code, but
not in the plan; it goes through `/pm idea` if wanted.
**Supersedes.** —

## D-011 · Storage layout: capture DB read-only, separate analysis, labels and fixture stores · 2026-11-02 · human
**Decision.**
- `capture.db` is input only. This project opens it read-only and never writes, migrates
  or deletes in it. Today it is a copy at `data/reference/capture.db`; later the project
  reads the extension's live file (path is config). A live file must be opened with
  `mode=ro`, never `immutable=1`, because the extension writes to it concurrently (WAL).
- Part 1 writes to a separate `data/analysis.db`, created and changed only by numbered
  migrations. The Progress Agent's read-only connection opens this file only.
- LeetCode verdicts live in a labels store (`data/labels/verdicts.csv` today) that only
  eval graders read — never `analysis.db`.
- Part 2's eval fixture is its own file (`evals/fixtures/progress.db`), same schema as
  `analysis.db`, fake data only.
- The extension's `attempts` / `attempt_gaps` tables are read by nothing.
- "Attempted at" stores the UTC timestamp and the local date; the timezone is config.
**Why.** The extension owns and keeps writing `capture.db`, so our migrations must never
touch real captured data. A verdict stored outside `analysis.db` cannot reach the agent
(rule 1) because the agent's connection cannot open it. The local-date finding is in
`docs/data/session-format.md` (an evening session lands on the next UTC day).
**Rejected.** Writing analysis tables into `capture.db` — mixes owners, risks real data,
and puts verdict-bearing `judge_events` in the agent's reach.
**Supersedes.** —

## D-012 · The condensed timeline is stored in analysis.db, read with run_sql · 2026-11-02 · human
**Decision.** The condenser writes each session's condensed timeline to `analysis.db`,
stamped with `condenser_version`. Part 1's LLM fields record the `condenser_version` they
read. Part 2 reads timelines with `run_sql`; there is no `get_session` tool. Rebuilding
replaces rows in one transaction and never deletes a stored timeline whose raw events are
no longer in the capture DB. A check flags analysis rows whose `condenser_version`
differs from the stored timeline's.
**Why.** The eval plan mentions a `get_session` tool, but D-001 gives the agent only
`run_sql`, and the agent cannot open `capture.db` (D-011) — so a stored timeline is the
only way the agent sees one. The timeline is derived and fully rebuildable from raw events
while they exist. Storing it makes a condenser/summary version mismatch visible instead of
silent.
**Rejected.** A second tool, `get_session`, that condenses live — supersedes D-001, and a
live timeline can silently disagree with summaries generated from an older condenser.
**Supersedes.** — (resolves the eval plan's `get_session` mention; plan edit proposed)

## D-013 · Condensed snapshots carry full code plus a change summary, not diffs · 2026-11-02 · human
**Decision.** Each kept snapshot in the condensed timeline shows the full code and a
one-line change summary against the previous kept snapshot (lines added / removed,
fraction of the file changed, and a `rewrite` flag at ≥ 50% changed). No raw diffs.
**Why.** Measured on 8 real sessions: full text ≈ 186 tokens per active minute (worst 253),
diffs ≈ 89 (`scripts/discovery/07_condense_estimate.py`, chars/4 estimate). A worst-case
60-minute session is ≈ 15k tokens — within budget for all three providers. A model reading
diffs must reconstruct the code, which adds an error source the failure-reason and summary
evals would wrongly blame on judgment. The change summary does the job the plan gave the
diff: making big rewrites stand out.
**Rejected.** The eval plan's literal "diff between snapshots" — about half the tokens, but
harder for the model to read correctly. Plan edit proposed.
**Supersedes.** —

## D-014 · Facts come from data; the LLM infers only what the data can't answer · 2026-11-02 · human
**Decision.** Status is the LeetCode verdict, read by code — no model predicts it. The
verdict, test counts and error message are ordinary inputs that any field and the Progress
Agent may read. Failure type is set by rule where the verdict decides it (Accepted → `none`,
Time Limit Exceeded → `too_slow`); otherwise the LLM chooses, with the verdict as input.
LLMs are used only for failure type when not determined, failure explanation, algorithm
type, timeline summary, and Part 2's judgment questions. Until submit capture is reliable,
a session with no captured or backfilled verdict has status `unknown`, not `not_submitted`.
**Why.** The goal is accurate analysis of real practice. Guessing a result LeetCode already
measured adds error for no gain — the extension's own analyzer called coin-change `failed`;
LeetCode says Accepted 191/191 (`data/labels/verdicts.csv`).
**Rejected.** (a) D-002 as written — model-predicted status in the analytics. (b) Real
verdict in the analytics plus model prediction kept as an eval-only exercise — keeps a
learning exercise, but adds a field and a leak fence the project doesn't need.
**Consequences.** Part 1's status eval (90% target, false-"Passed" rate) is removed;
status gets exact unit tests instead. Rule 1 in `CLAUDE.md` needs rewording (human's file —
proposed, not applied). Submit capture in the extension becomes critical path (`/pm idea`).
The human-written eval labels (failure type, algorithm, key facts, expected answers) are
still never model inputs.
**Supersedes.** D-002

## D-015 · Capture (extension + ingest server) lives in this repo; capture only · 2026-11-02 · human
**Decision.**
- The browser extension and its ingest server move into this repo under `ux-extension/`
  and become the source of truth. `/Users/milestucker/dev_work/leetcode-analyzer` stops being
  run; its existing `data/leetcode.db` is kept untouched as a backup.
- Only capture moves: `extension/` and the ingest path of `server/` (`ingest.ts`, `db.ts`,
  `judge.ts`, `sessions.ts`, `taxonomy.ts`, `config.ts`, `seed-problems.ts`, `diff.ts` if
  used). The old analyzer (`server/src/agent/`), MCP server (`server/src/mcp/`), dashboard,
  evals and traces are removed from the copy, and the ingest server no longer runs an
  analysis when a session ends.
- The ingest server is the **only writer** of the capture DB. Everything in `src/tutor/`
  still opens it read-only (D-011 unchanged). The live file is `data/capture.db` in this
  repo (gitignored), seeded once by an SQLite `.backup` of the old live DB with the old
  server stopped. `capture.path` in config points there.
**Why.** Debugging T-001 across two repos meant a byte-identical copy here and a running
copy there. One repo means one place to fix, test and run capture, and the loader's config
points at a file this repo owns. The old analyzer, MCP and dashboard duplicate Part 1 and
Part 2, which this project builds itself as the learning exercise. Keeping them would add
a second, competing implementation, and the second LLM caller would break rule 5.
**Rejected.** Moving the whole old repo (duplicate Part 1/2, a second LLM client).
Keeping capture in its own repo (two copies drift; T-001 was already slowed by it).
**Supersedes.** — (amends D-011: the capture DB is now in this repo, still read-only to `src/tutor/`)

## D-016 · Evals load real sessions from the frozen copy; the pipeline reads the live DB · 2026-11-02 · human
**Decision.** Real eval cases (`capture_session_id`) always load from
`paths.eval_capture_db` = `data/reference/capture.db`, opened `immutable=1`. The pipeline
and the agent's data path read the live `paths.capture_db` = `data/capture.db` with
`mode=ro`. The loader refuses `immutable=1` on the live file. Replacing the frozen copy is
a dataset change: new `dataset_version`, with a written reason (rule 10).
**Why.** With capture in this repo (D-015), the live file changes as the human practises,
including sessions the server closes later. A dataset version must name fixed inputs, or two
eval numbers can differ for reasons that are neither the prompt nor the model (rule 7).
**Rejected.** A single live path for everything: simpler config, but the inputs aren't
reproducible.
**Supersedes.** — (amends D-011's "later the project reads the extension's live file": true
for the pipeline, never for evals)

## D-017 · Synthetic sessions are generated by Claude from human-approved specs, then human-reviewed · 2026-11-02 · human
**Decision.** About 22 synthetic sessions are generated, not hand-written. Each starts from
a spec (problem, verdict, failure type, algorithms, story, key facts) that the human writes
or approves; the spec is the label. The model (`llm.generator` = Claude, through the one
client wrapper and a versioned prompt `prompts/generators/session/v<N>.md`) writes only the
code snapshots and Run output. Code builds the `Session`, copying the verdict and test
counts from the spec. Deterministic checks (schema, timing, ±20% shape, and a leak check
that no label or key-fact text appears in the session) run before the human reviews each
session. The runner refuses unreviewed sessions. Generator, `checks.py` and the generator
prompt are tester-owned (`CLAUDE.md` rule 11 edit proposed in architecture §15.3).
**Why.** Real data gives only ~8 usable cases, 7 of them Accepted (G7), and hand-writing 22
realistic multi-snapshot sessions is slow. Generation is cheap; the spec keeps the labels
human, the leak check keeps them out of the inputs (rule 1), and review keeps
the human the judge of labels (rule 11).
**Rejected.** Hand-written sessions (too slow for 22). The model also writing the labels
(the labels would then be model opinions graded against themselves).
**Supersedes.** —

## D-018 · Default model is OpenAI; Claude generates synthetic data; adapter order changes · 2026-11-02 · human
**Decision.** `llm.default` = `openai:gpt-5.5` (id taken from the old repo's default; the
human confirms it). `llm.generator` = `anthropic:claude-opus-5-5`; `generate-sessions` refuses
to run if the generator and the default model share a provider. Adapter order: OpenAI first
(M0's logged-call checkpoint), Anthropic by M2 (generation), Gemini at build step 7.
Every result record reports metrics overall, real-only and synthetic-only.
**Why.** The human chose OpenAI as the default. A model generating its own test inputs can
inflate its scores, so the generator comes from another provider. The real-only and
synthetic-only split shows any leftover generator bias, including at M7, where Claude is
also compared. Both API keys are already in `.env`.
**Rejected.** Generating with the default model: one adapter fewer early, but its scores
would then be measured on inputs it wrote itself.
**Supersedes.** — (amends D-008's order "Claude first, OpenAI/Gemini at step 7")

## D-019 · Verdict text → status by a fixed table; the text is also kept verbatim · 2026-11-02 · human
**Decision.** Status is looked up from the final submit's verdict text (`check/`
`status_msg`, as stored in `judge_events.status`). The table: Accepted → `passed`;
Wrong Answer and Output Limit Exceeded → `failed_wrong_answer`; Time Limit Exceeded and
Memory Limit Exceeded → `failed_too_slow`; Runtime Error and Compile Error →
`failed_runtime_error`; any other text → `unknown`, logged as `unmapped_verdict`.
`sessions.leetcode_verdict` keeps the exact text, so the Progress Agent can tell MLE from
TLE with `run_sql`.
**Why.** LeetCode states the verdict exactly in the `check/` response (the human showed
OLE and TLE responses, `judger_status_code` 13 for OLE), so no model is involved (D-014).
The plan's status list has five buckets, so the extra verdicts need a home: MLE is a
complexity failure like TLE (and the rule then sets failure type `too_slow`); OLE means the
returned output was wrong in size or shape; Compile Error means the code never ran.
Unknown texts don't raise, so a new LeetCode verdict can't stop the pipeline, but the log
shows it.
**Rejected.** Adding status values for each verdict (changes the plan's status list for
rare cases; the verbatim text already carries the detail). Raising on unmapped text.
**Supersedes.** —

## D-020 · Output Limit Exceeded maps to `failed_runtime_error`, not `failed_wrong_answer` · 2026-11-02 · human
**Decision.** In D-019's table, Output Limit Exceeded → `failed_runtime_error`. The rest of
D-019 stands.
**Why.** The human: OLE generally means too many print statements, i.e. the program's
stdout overflowed. The answer it returned may be correct. That is a problem with how the
run behaved (like a crash), not a wrong answer, and labelling it wrong-answer would pull
those sessions into "wrong approach / edge case" analytics. Failure type for these stays an
LLM call with the verdict and error in its input (no rule), which will usually give
`implementation_bug`.
**Supersedes.** D-019 (the OLE row only)

## D-021 · Build choices for T-002 / T-003 · 2026-11-02 · builder (human approved the list)
**Decision.**
1. **Capture stops writing analysis state.** `endSession` no longer sets
   `sessions.analysis_status = 'pending'`, and `markAccepted` (a late Accepted) only sets
   `end_reason = 'accepted'`: it no longer deletes that session's `attempts` rows. New
   sessions keep `analysis_status = 'open'` forever. `attempts` / `attempt_gaps` keep their old
   rows and get no new ones.
2. **Popup:** the "View dashboard" / "View problems" buttons and the "Analysis" row were
   removed. They pointed at the deleted dashboard and analyzer.
3. **`tutor.toml` is the only home of defaults.** The config models have no in-code defaults,
   except for keys the architecture says are unset by default.
4. **`tutor-eval` lives in `tutor/cli.py` (`eval_main`)** until an evals package exists.
5. **Run ids** are `YYYYmmddTHHMMSSZ-<8 hex>`: sortable by start time, random suffix.
6. **Log lines:** `ts`, `run_id` and `event` can't be overridden by extra fields.
7. **Seeding** is a one-off stdlib script, `scripts/seed_capture_db.py`, not product code. It
   uses SQLite's backup API (which captures `-wal` content), checks the hash before and after,
   and refuses to overwrite.
8. `seed:problems` (calls LeetCode's public GraphQL list) is kept as a manual script.
**Why.** (1) Deleting `attempts` rows would destroy legacy data on a late Accepted, and
`'pending'` would advertise an analysis that will never run. (3) Two copies of defaults drift.
(7) A plain file copy would miss writes still in the old server's `-wal` file (it was not
shut down cleanly; the WAL was 4 MB).
**Supersedes.** —

## D-022 · Output Limit Exceeded gets its own status, `failed_output_limit` · 2026-11-02 · human
**Decision.** The status list gains `failed_output_limit`, and LeetCode's "Output Limit
Exceeded" maps to it. It no longer maps to `failed_runtime_error` (D-020) or
`failed_wrong_answer` (D-019). The status CHECK in `analysis.db` and the eval plan's status
list include it. Failure type for these sessions has no rule: the LLM decides, with the
verdict and error detail in its input.
**Why.** The human wants OLE visible as its own outcome, like TLE. It usually means too many
print statements, a habit worth tracking on its own, not a wrong answer or a crash. Mapping
it to another status would hide it in Part 2's per-status counts.
**Cost.** One more status value. `analysis.db` hasn't been created yet (T-008 is ⬜), so no
migration is needed: the change goes straight into `0001_init.sql`.
**Supersedes.** D-020 (and D-019's OLE row)
