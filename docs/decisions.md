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

## D-023 · Capture matches check/ URLs by an optional version segment and dedupes by submission id per problem · 2026-11-02 · builder (human approved)
**Decision.**
1. The page hook matches `/submissions/detail/<id>/(v<digits>/)?check/`, not the literal
   `/check/`. `judge.ts`'s URL fallback uses the same pattern.
2. A judge result is posted even when reading the editor throws; `code` is then null.
3. A result whose LeetCode `submission_id` is already stored for the same problem is ignored,
   whichever session is open now. The check runs before a session is chosen. The DB's unique
   index stays per `(session_id, submission_id)`: the capture schema is frozen, so the rule
   lives in code.
**Why.** (1) LeetCode moved Submit polling to `/v2/check/` and every submit was lost silently.
Matching `v\d+` means a future `/v3/` doesn't repeat that. (2) The verdict is the fact status
depends on (D-014); the code snapshot is secondary. (3) An Accepted ends the session, so a
repeat of the same result a second later used to open a new session holding a copy. LeetCode
ids identify a submission exactly, which a time window can't.
**Supersedes.** —

## D-024 · Loader and prompt-loader interfaces the tests pin · 2026-11-03 · tester (human approved)
**Decision.**
1. `SubmitEvent.verdict` is LeetCode's verdict text verbatim (`str`), not the `Verdict` enum.
   `Verdict` still lists the 7 known values for the status mapping (M1), which handles text
   it doesn't know as `unknown` (§4.3).
2. `submit_capture_reliable` compares the session's start date in `time.timezone`
   (America/New_York) with `capture.submits_reliable_since`, a date (the human set
   2026-11-04, T-001).
3. `verdicts.csv` rows match sessions by session id only. When a session has both a captured
   submit and a CSV row: the same verdict as the last captured submit means the captured one
   is kept and the CSV row is dropped; a different verdict raises `VerdictConflict`. The CSV
   stays frozen for the 8 pre-fix sessions; new sessions rely on captured submits. A missing
   CSV file means no backfill.
4. Loader: `tutor.capture.loader.CaptureLoader(path, *, mode: "ro" | "immutable", settings,
   run_id=None)` with `.iter_sessions(since=None)` (ordered by `started_at`) and
   `.load_session(id)` (`LookupError` if unknown or excluded). A bad mode, or `immutable` on
   `paths.capture_db` (compared after resolving the path), raises `ValueError`.
   `VerdictConflict` and `CaptureFormatError` live in the same module; a timestamp error names
   the session, the table and the row id.
5. Exclusions are logged to `<paths.logs>/pipeline.jsonl` as `session_excluded` with
   `reason` `no_activity` (≤ 1 snapshot and no judge events) or `human_exclude` (a CSV
   `EXCLUDE` row; it wins when both apply).
6. Prompts: `tutor.prompts.load_prompt(name, version, *, root=None)` → `LoadedPrompt` with
   `text` = the body after the front matter and `sha256` = the hash of the whole file's
   bytes. `LoadedPrompt.substitute(mapping)`. `PromptError` for: a missing file (the message
   names the path), no front matter, a front-matter name or version that differs from the
   path, a `$var` in the body that isn't declared, a declared variable the body never uses,
   and a missing or extra variable at substitution.
7. `prompts/manifest.json` is `{"<name>/v<N>.md": "<sha256>"}`, keys relative to `prompts/`,
   judges and generators included. `tutor prompts check [--root DIR]` exits 0 when every
   file matches its entry, else 1, naming each file that was edited, is unlisted, or is gone.
**Why.** The architecture names these pieces (§4.1, §4.4, §7) but not their signatures or edge
rules, and black-box tests need them fixed before the build. (1) An enum would make the
loader crash on a new LeetCode verdict, which §4.3 says must not raise. (2) The human thinks
in local dates; `attempted_date_local` uses the same timezone. (3) Overlap isn't expected, so
a disagreement can only be a data error; a captured submit is the better record when both agree.
**Supersedes.** — (narrows §4.1's `verdict: Verdict` to `str`)

## D-025 · Loader and prompt-loader details left open by D-024 · 2026-11-03 · builder (human approved)
**Decision.**
1. Prompt front matter is read by a small parser that accepts only flat `key: value` lines and
   `key: [a, b]` lists, the form §7 shows. Anything else is a `PromptError`. No YAML dependency.
2. A capture row the models can't accept is a `CaptureFormatError` naming the session (and the
   row where there is one): a session whose slug has no `problems` row, a NULL difficulty or
   snapshot language, a `tags` value that isn't JSON, a judge event whose kind isn't run or
   submit. None occur in today's data.
3. `CaptureLoader(run_id=None)` makes a fresh `new_run_id()`, so every exclusion log line has a
   run id.
**Why.** (1) Six lines of front matter don't justify a dependency, and a strict subset can't be
misread. If prompts ever need richer metadata, switching to YAML is a contained change. (2)
The loader is the validation boundary: a row it can't represent faithfully stops the load
rather than becoming a guessed default that later reads as a fact. (3) Log lines without a run
id can't be tied back to the run that wrote them (§13).
**Supersedes.** —

## D-026 · Stuck periods deferred; the timeline reports course correction instead · 2026-11-03 · human
**Decision.** The condensing step does not flag stuck periods. The timeline summary says
whether the first approach was on the right track and, if not, whether and roughly when the
user course-corrected; its checklist checks that, and that it doesn't invent a correction.
The human labels each dataset session with `course_correction = {first_approach_on_track,
corrected, at_min}`. The condenser is unchanged: rewrite flags (D-013) already mark new
approaches. Rule-based stuck periods go to Deferred.
**Why.** Measured on all 26 real sessions (8 frozen + 18 live,
`scripts/discovery/18_stuck_periods.py`): "3+ ticks / 6+ min with < 5 lines changed" never
fired; even < 10 lines, and net change instead of churn, found nothing. Snapshots are saved
on every change (~5 s) and no real session has a 4-minute gap, so the only hit was one page
left open. "3+ failing runs with the same error" found 3 periods only when "same" meant the
same status; with the error text it found 1, because output/expected values change as code
is edited. A rule that never fires can't be tuned on real sessions, as the plan requires.
Whether an approach was wrong is a judgment, which belongs to the LLM field and a human label.
**Rejected.** (a) Keep rule B and exercise it only with synthetic sessions: tests a behaviour
real data never shows. (b) Rule A alone with "same status": catches repeated wrong answers but
not wrong approaches, and its 3 periods were not yet confirmed by the human.
**Supersedes.** — (reverses the eval plan's 2026-11-03 stuck-period additions)

## D-027 · LLM client interfaces the T-006 tests pin · 2026-11-03 · tester (human approved)
**Decision.**
1. `tutor.llm` exports `LLMClient`, `ModelRef`, `LLMResult`, `Usage`, `LLMError` and its
   subclasses `LLMConfigError`, `LLMOutputInvalid`, `LLMProviderError`.
   `LLMClient(settings, *, adapters=None, pricing_path=None, sleep=time.sleep)`: `adapters` maps
   provider → adapter (None = the real ones), `pricing_path` defaults to `config/pricing.toml`.
2. Adapter interface: `structured(*, model, messages: list[Message], schema: dict, schema_name,
   timeout_s) -> tutor.llm.adapters.AdapterResponse(text, input_tokens, output_tokens, request,
   response)`. The client passes `output.model_json_schema()` unchanged; strict-mode rewriting is
   the adapter's job. Adapters raise `LLMProviderError(message, *, retryable, status_code=None)`
   and the client retries only when `retryable`. The OpenAI adapter turns off the SDK's own
   retries and honours the SDK's `OPENAI_BASE_URL`.
3. Model choice: `model=` argument > `llm.fields.<field>` > `llm.default`.
   `ModelRef.parse("provider:model")`; a malformed ref, or a provider with no adapter yet, is
   `LLMConfigError`. The `--model` CLI flag arrives with T-007's `tutor smoke`, the first
   command that calls an LLM.
4. Backoff before transient retry k: 2^k s + jitter in [0, 1). Invalid-output retries append the
   validation error as a `user` message after the original conversation.
5. `LLMResult.usage` sums tokens and cost over every attempt. A provider-error attempt logs 0
   tokens and $0. Bodies: `<paths.logs>/llm_bodies/<call_id>.json`, one JSON file per call.
6. The scripted `FakeAdapter` is tester-owned (`tests/_llm_fake.py`). The real adapter is
   checked against a fake OpenAI server on loopback.
**Why.** §6 gives the client's interface, not the seam the tests need to inject a provider, the
jitter range, or what usage means across retries. (6): the fake grades the client's retry and
logging logic, so the builder doesn't write it (rule 11). The loopback server tests the real SDK
path, so hidden SDK retries or a key in a log would be caught. (5): the failed attempt was paid
for, so eval-run cost totals stay honest.
**Supersedes.** —

## D-028 · LLM client details left open by D-027 · 2026-11-03 · builder (human approved)
**Decision.**
1. The OpenAI adapter uses the Responses API, with `text.format` set to a strict
   `json_schema`, and `store=False`.
2. The strict-schema rewrite is our own `strict_schema()` in `adapters/openai.py`. It applies
   OpenAI's documented rules: every object has `additionalProperties: false` and all of its
   properties required, `default` is dropped, and a `$ref` with sibling keys is inlined. It does
   not use the SDK's private `openai.lib._pydantic` helper or `responses.parse()`.
3. An invalid-output retry appends two messages: the bad output as `assistant`, then the
   validation error (`field: problem` lines) as `user`.
4. `call_id` is 16 random hex characters. The body file is `{"call_id", "exchanges": [{attempt,
   request, response | error}]}`, rewritten after each attempt. The key is `exchanges`, not
   `attempts`, because the extension-analysis fence (§4.3 #3) reserves a quoted `"attempts"`.
5. Prices are read from `pricing.toml` on every call, so an edited price takes effect on the
   next call without a restart.
**Why.** (1) The Responses API is OpenAI's current API for new work. With `store=False`, OpenAI
doesn't keep the session code; `llm_bodies/` already holds it. (2) A private helper can change in
any SDK release. `responses.parse()` validates inside the SDK and raises before token counts are
returned, which breaks per-attempt cost logging and the client's own validation (§6.1). Our
rewrite depends only on the documented rules. If those change, the API rejects the schema with
a 400 error, so the failure is loud. (3) The model sees what it got wrong, not only that it was
wrong.
**Supersedes.** —

## D-029 · `tutor smoke` interface the T-007 tests pin · 2026-11-03 · tester (human approved)
**Decision.** `tutor smoke --session <id> [--model provider:model]`:
- loads the session from `paths.eval_capture_db` (the frozen copy, `immutable`);
- fills `prompts/smoke/v1.md` with the problem title;
- makes one `structured()` call, field `smoke`, output `{problem_slug: str}`;
- prints one JSON line to stdout: `{"session_id", "output", "call_id", "model": "provider:model",
  "cost_usd"}`, and exits 0.

Any error goes to stderr with a non-zero exit. An unknown or excluded session, or a bad
`--model`, sends no request. `prompts/smoke/v1.md` gets a manifest entry like any prompt. The
fake OpenAI server moves to `tests/_fake_openai.py`, shared by the T-006 contract test and the
T-007 tests.
**Why.** One machine-readable line lets the test, and you, check the output, the call id and the
cost without parsing prose. Reading the frozen copy keeps the checkpoint reproducible: the
live DB changes every time you practise.
**Supersedes.** —

## D-030 · CLI error exit code; manifest entries by hand for now · 2026-11-03 · builder (human approved)
**Decision.** (1) A `tutor` command exits 1 on any error it handles: unknown or excluded session,
`LLMError`, `ConfigError`, `CaptureFormatError` or `PromptError`. The message goes to stderr
as `error: …`. argparse's own usage errors keep exit 2. (2) `LLMClient.model_for(field, model=None)`
is public, so callers that report the model they used (`smoke`, later the eval runner) use the
client's own lookup order rather than repeating it. (3) A new prompt's `prompts/manifest.json`
entry is written by hand: its sha256, keys sorted. A `tutor prompts lock` command is still an
open `/pm` follow-up.
**Why.** (1) Callers and tests need one exit code for "it ran and failed", separate from
"you called it wrong". (2) A second copy of the lookup order could drift, and then the reported
model would differ from the one called. (3) Building a lock command is outside T-007's scope.
**Supersedes.** —

## D-031 · Lint + type gate: ruff (narrow rule set) + mypy on src/ · 2026-11-03 · human
**Decision.** The `/test run` "Lint + types" gate is `uv run ruff check src tests && uv run mypy`.
- **Ruff** checks `src/` and `tests/` with exactly `E4, E7, E9, F`: undefined names, unused
  imports and variables, import placement, statement and syntax errors.
- **mypy** checks `src/` only, with the pydantic plugin.
- Both are dev dependencies.
**Why.** The human chose the lean gate. It catches real bugs and is clean today without editing
tester-owned files. The wider sets (I, B, UP and others) and type-checking `tests/` would mean
about 40 mostly cosmetic edits to test files only `/test write` may touch. The rules are named,
not left to ruff's defaults, because ruff 0.17's defaults are much wider than 0.8's: the same
config would have gone from 0 findings to 24 on an upgrade. mypy over pyright: a plain Python
dev dependency, with no Node download.
**Rejected.** The strict gate (wider ruff sets, plus types over `tests/`): about one extra session,
for little bug-catching value.
**Supersedes.** —

## D-032 · Migration interfaces the T-008 tests pin · 2026-11-03 · tester (human approved)
**Decision.**
- `tutor.db.migrate.migrate(db_path, *, settings, migrations_dir=None) -> list[int]` applies the
  pending migrations, each in its own transaction, records each one in `schema_migrations`, and
  returns the versions it applied. `migrations_dir` defaults to `src/tutor/db/migrations/`.
- `MigrationError` covers a refused target, and a migration that failed and was rolled back.
- `tutor migrate [--db PATH]`; `PATH` defaults to `paths.analysis_db`. It exits 1 with a message on
  stderr on error (D-030).
- `schema_migrations.name` is the file name with the number and `.sql` removed: `0001_init.sql`
  → `init`.
- The refusal covers both `paths.capture_db` and `paths.eval_capture_db`, compared after resolving
  symlinks and `..`, and happens before the file is opened.
- The acceptance test checks `0001_init.sql` against the SQL block in architecture §3.2: both are
  applied to empty databases and the schemas compared, ignoring comments and whitespace.
**Why.** `migrations_dir` lets a test supply a migration that fails partway, which is the only
way to check the one-transaction rule. Comparing against the doc's own DDL means the migration
and the architecture can't drift apart unnoticed. The frozen copy is refused as well as the live
DB because it must never change either (D-016).
**Supersedes.** —

## D-033 · Migration runner details left open by D-032 · 2026-11-03 · builder (human approved)
**Decision.**
1. Each migration runs as `BEGIN;` + the file through `executescript`, on an autocommit
   connection (`isolation_level=None`). The `schema_migrations` row is then inserted with bound
   parameters and `COMMIT` sent. On any `sqlite3.Error` the runner sends `ROLLBACK` and raises
   `MigrationError` naming the file.
2. A migration file may not contain `BEGIN`, `COMMIT`, `ROLLBACK` or `END` statements; `migrate`
   refuses such a file before running it.
3. `migrate` doesn't check `migrations/manifest.json` at run time. The contract test enforces it.
**Why.** (1) On its own, `executescript` commits before running and keeps whatever ran before a
failure. Starting the script with `BEGIN` puts the file and its version row in one
transaction. Splitting files into statements would need a SQL splitter, which is fragile around
semicolons inside strings. (2) A transaction statement inside a file would silently break that
rule. (3) A hash check at run time would block `tutor migrate` locally for a mismatch the
contract test already reports.
**Supersedes.** —

## D-034 · Condenser gaps settled for the T-009 tests · 2026-11-03 · human
**Decision.**
1. `Moment.submit: SubmitEvent | None` carries a submit's verdict, test counts and error
   (kind='submit'), alongside the existing `run` field. Architecture §4.1 updated.
2. FINAL is the last timed Moment. Its `ts` is the latest snapshot or event timestamp, and its
   code is the last snapshot's. Only backfilled submits (`ts=None`) follow it: they take FINAL's
   `elapsed_min` and point at the final code. Time to finish is unchanged: it still ends at the
   last captured submit (§5.1).
3. A rewrite renders as ` · REWRITE` at the end of the change line.
4. Smaller pins, chosen by the tester without a separate question:
   - a timed Moment's `ts` is its tick (`t0 + k·interval_s`, k ≥ 1, ticks up to and including
     `t_end`);
   - `code_ref` is an index into `moments`;
   - a Moment with `code=None` has `change=None`, except a timed Moment whose code was dropped
     for the budget, which keeps its change;
   - the render's "N runs · M submits" counts captured submits only, as the §5.5 example does.
**Why.** (1) The render needs a submit's verdict, and `Moment` had nowhere to keep it. (2) Read
literally, "the last snapshot, ordered by ts" puts FINAL in the middle of the timeline whenever
the user keeps typing or runs after the last submit. (3) D-026 relies on rewrite flags to show
new approaches to the timeline model. A percentage leaves that for the model to infer.
**Supersedes.** — (amends architecture §4.1, §5.2 and §5.5)

## D-035 · Condenser build details left open by §5 and D-034 · 2026-11-03 · builder (human approved)
**Decision.**
1. `CondensedSession.language`: the last snapshot's language, used to fence code in the render.
2. Every Moment that shows new code puts its change summary on its header line, runs and
   submits included: `RUN · <status> · 0/2 passed · code as of 30.0 s earlier · +1 −0 lines ·
   20% changed`.
3. Each Moment renders as: a header, then the error line if there is one, then either the code
   block or a placeholder line. The placeholders are "(code unchanged since X min)", "(code
   omitted to fit the token budget)" for dropped timed code, and "(no code captured yet)" for an
   event before the first snapshot.
4. "N runs · M submits" is always plural, exactly as §5.5 writes it.
5. `error_detail` is cut inside `condense`, on the Moment's copy of the event, so `render` takes
   no settings. `session_times()` is the one §5.1 helper. T-010's time to finish must call it.
**Why.** (1) §5.5 asks for code fenced in the session language, but `render(c)` receives only the
condensed session, which had no field for it. (2) A rewrite just before a run is as important
to see as one at a tick. (5) `render` stays a function of `c` alone, so a stored
`rendered_text` can always be regenerated from `timeline_json`.
**Supersedes.** — (adds one field to §4.1's `CondensedSession`)

## D-036 · Deterministic-field interfaces the T-010 tests pin · 2026-11-03 · tester (human approved)
**Decision.**
- `tutor.models` gains `Status` and `StatusSource`, StrEnums whose values are exactly the §3.2
  CHECK lists.
- `tutor.fields.deterministic` provides:
  - `problem(session) -> Problem`;
  - `time_to_finish(session) -> float`, equal to `condense(session).duration_min` through
    `session_times()` (D-035);
  - `attempted_at(session, *, settings) -> (datetime UTC, date)`: the first event in UTC, and its
    date in `time.timezone`;
  - `status(session, *, settings, run_id) -> StatusResult(status, status_source,
    leetcode_verdict, tests_passed, tests_total)`.
- An unmapped verdict gives `unknown` and writes one `unmapped_verdict` line, with `session_id`
  and `verdict`, to `<paths.logs>/pipeline.jsonl`. It never raises.
**Why.** Architecture §2 names the module but not its functions. `settings` is passed in rather
than loaded inside, so the tests can pin the timezone and the log path.
**Supersedes.** —

## D-037 · Pipeline interfaces the T-011 tests pin · 2026-11-03 · tester (human approved)
**Decision.**
- `tutor analyze [--since YYYY-MM-DD]` reads `paths.capture_db` (`mode=ro`) and upserts `problems`,
  `sessions` and `condensed_timelines` in one transaction. `--since` is a date in `time.timezone`:
  sessions that started on or after its local midnight.
- `tutor rebuild-timelines` re-condenses every loadable session in one transaction. A stored
  timeline whose session no longer loads is kept and logged as `timeline_orphaned`.
- `tutor check` exits 1, naming each stale session, when a `session_analysis` row's
  `condenser_version` differs from its timeline's.
- All three exit 0 on success and 1 on error (D-030). `analyze` refuses a missing or unmigrated
  `analysis.db` without creating it, and its message points to `tutor migrate`.
- `pipeline.jsonl` gets `session_loaded` and `session_condensed` for each kept session, plus the
  loader's `session_excluded` with its `reason`. Each line has `session_id` and `run_id`, and one
  command run uses one `run_id`.
- The condenser's `interval_s`, `error_max_chars` and `token_budget` come from
  `settings.condenser`.
- `submit_count` counts captured submits only (§3.2).
**Why.** §5.6 and §13 give the behaviour but not the command names' exit codes, the log event
names, or what `--since` compares. A failed run must leave the database as it was, or a
half-written `analysis.db` would read as complete.
**Supersedes.** —

## D-038 · Pipeline build details left open by D-037 · 2026-11-03 · builder (human approved)
**Decision.**
1. `rebuild-timelines` covers sessions that already have a `sessions` row. A loadable session
   that was never analyzed is skipped and counted in the summary.
2. `check` treats an analysis row with no stored timeline as stale, as well as one with a
   different `condenser_version`.
3. Stored timestamps (`attempted_at_utc`, `loaded_at`, `built_at`) are ISO-8601 UTC with
   milliseconds and `Z`, as capture writes them.
4. Every command condenses everything in memory first, then writes it all in one transaction.
5. `open_analysis_db` opens with `mode=rw`, so a missing file is an error and never created.
   It refuses capture paths through `migrate.refuse_capture`, now public.
**Why.** (1) Adding a session is `analyze`'s job; a rebuild that inserted timelines would leave
rows with no `sessions` row. (2) Fields built from a timeline that's no longer stored are as
untrustworthy as fields built from an old version. (4) A condense failure then happens before
the first write, and a write lock isn't held while condensing.
**Supersedes.** —

## D-039 · Specs say what "on track" would have been, as algorithm labels only · 2026-11-07 · human
**Decision.** A synthetic spec's `story` gains `on_track_algorithms`. When the first approach was
off track, it holds 1–2 labels from the algorithm list for what would have worked; when the first
approach was on track, it is `null`. It is a label: never a model input, and not graded directly.
`labels.algorithms` still means what the final code does, which is what the algorithm field is
graded on. Specs are drafted with the `synthetic-spec` skill and checked by
`evals/generate/check_specs.py`. The checker also enforces that `wrong_approach` means off track
and never corrected, and warns when the final algorithms equal the on-track ones on an
off-track spec.
**Why.** "Off track" is a claim about what on track would have been. Written down, it is checkable
by the human, gives the generator a target for course corrections, and lets the
failure-explanation judge check a suggested alternative. Labels rather than prose or code, because
the eval plan rules out an expected approach with code.
**Supersedes.** — (adds one field to the §8.5 spec)

## D-040 · The dataset must stay balanced; the spec checker measures it · 2026-11-07 · human
**Decision.** Variety is a checked requirement. `check_specs.py` reports the distribution over
the whole dataset (with `--with-real`, the frozen copy's sessions count too) and prints a `skew`
line, from 8 sessions on, when any of these rules breaks:
- no single status above 35%;
- no single failure type above 30%;
- no difficulty above 50%, and Easy, Medium and Hard each at least 15%;
- across the time buckets under 10, 10–25, 25–45 and 45–60 min, none above 40% and each at least 10%;
- no algorithm label on more than 20% of sessions;
- no synthetic spec reusing a problem.

The `synthetic-spec` skill drafts each batch against those skew lines.
**Why.** The human: variety of problems, verdicts and time spent, without skewing one way. The real
sessions already lean hard: 7 of 8 Accepted, no Hard problems, none over 25 minutes. Left alone,
a model could score well by always saying "passed", and long timelines would never be tested.
Thresholds are starting points, and a change to them is a recorded decision.
**Supersedes.** —

## D-041 · Balance rules for difficulty and time spent changed · 2026-11-07 · human
**Decision.** Difficulty is reported but no longer balanced. Time spent uses three buckets:
under 10, 10–30, and over 30 minutes. Most sessions (at least 50%) must be 10–30 min, with at
least one under 10 and at least one over 30. Every other D-040 rule stands.
**Why.** The human: "we won't be practicing many hard problems. and most problems should be between
10-30 minutes. but at least have 1 that is under 10 and one that is over 30." A dataset forced to
15% Hard and spread across 45–60 minutes wouldn't look like the practice it's meant to evaluate.
**Supersedes.** D-040 (the difficulty and time-spent rules only)

## D-042 · Synthetic sessions are Python only, for now · 2026-11-07 · human
**Decision.** Every synthetic spec uses `python3`, and the spec checker enforces it. A Python
Compile Error spec means a `SyntaxError` or `IndentationError`. A misspelt name or field fails at
runtime (Runtime Error), not at compile time.
**Why.** The human: "i want to keep everything python right now". Every real session is Python
too, so a second language would add a variable the evals aren't trying to measure.
**Supersedes.** —

## D-043 · Synthetic final code is human-written; giveaway comments are removed · 2026-11-07 · human
**Decision.**
1. The human writes each synthetic session's **final code** (generated with Claude, then checked on
   LeetCode itself). It lives in `evals/data/sessions/synthetic/final_code/<id>.py`, one file per
   spec, with the class named as LeetCode's editor names it.
2. The session generator writes only the **earlier** snapshots leading up to that code, plus each
   Run's output. The final snapshot is the human's file, unchanged.
3. Comments that state the bug or name the algorithm used or needed are removed before code goes
   into the dataset. Examples: "should be max(…)", "no overflow check", "bug: …",
   "AttributeError on empty tree". Ordinary comments stay: TODOs, notes on what a variable holds,
   and step notes like "# delete word1[i]".
**Why.** Final code checked on LeetCode makes the verdict and the story real rather than imagined.
Comments that state the answer would let the failure-reason and algorithm evals be passed by
reading them, and real practice code doesn't annotate its own bugs. The generator's leak check
(§8.5) still runs on everything.
**Supersedes.** D-017 in part: the model no longer writes the final snapshot.

## D-044 · `prefix_sum` joins the algorithm labels · 2026-11-07 · human
**Decision.** The fixed algorithm list gains a 19th label, `prefix_sum`, covering prefix sums and
products. The eval plan, architecture §4.2, the spec checker and the skill already list it.
`analysis.db` gets it through migration `0002_add_prefix_sum.sql`, which recreates
`session_algorithms` with the longer `label` CHECK and copies existing rows. It is a tracker task
(T-014), because applied migrations are never edited (§3.3). syn-021 is labelled `prefix_sum`, and
syn-011's on-track algorithms become `prefix_sum, hash_map`.
**Why.** The human: it is "the category that is more accurate". Product of Array Except Self and
Subarray Sum Equals K are prefix-sum problems, and no existing label fit (`math` was a stand-in).
The CHECK keeps an off-list label out of the database, so it must list every valid label. The
table is empty everywhere today, which makes this the cheapest moment to change it.
**Supersedes.** — (extends the eval plan's label list)

## D-045 · The synthetic spec set closes at 20 for now · 2026-11-07 · human
**Decision.** Synthetic specs stop at 20 (syn-001 – syn-023, with syn-008, syn-014 and syn-015
retired), each with human-written final code checked on LeetCode. With the 8 frozen real sessions
the dataset is 28, not 30. Known gap: no Compile Error session. The 20/10 dev/test split is
re-proportioned when the dataset is assembled (M2). More specs, or more real sessions after
refreshing the frozen copy, can be added later as a dataset-version change.
**Why.** The human: "i think this is good enough for now". The set covers every other status,
every failure type and 18 of 19 algorithm labels, with no skew. Two more specs would only fill
Compile Error, a status that never needs an LLM call.
**Supersedes.** — (the eval plan's "30 sessions" becomes 28 for dev-v1)

## D-046 · The session generator runs as the tester's module, not a `tutor-eval` subcommand · 2026-11-07 · pm (human approved the M2 plan)
**Decision.** The synthetic-session generator lives in `evals/generate/` (tester-owned, D-017) and
runs as `uv run python -m evals.generate.sessions …`, rather than the `tutor-eval
generate-sessions` that §8.5 names.
**Why.** A `tutor-eval` subcommand would put generator wiring in `src/tutor/cli.py`, which is
builder code, while the generator itself is tester-owned. That splits one tool across two owners
for no gain. The generator still calls the LLM only through `LLMClient` (rule 5).
**Supersedes.** — (amends §8.5's command name)

## D-047 · A model refusal is a non-retryable provider error · 2026-11-07 · tester (human approved)
**Decision.** When a provider ends a response with a refusal (Anthropic `stop_reason: "refusal"`),
the adapter raises `LLMProviderError(retryable=False)` with "refusal" in the message. The client
does not retry it, and the field or case records it as an error. No server-side `fallbacks` model
is configured for now.
**Why.** Re-sending the same request would very likely be refused again, and it costs money each
time. Treating it as invalid output would spend the output retry on a request that can't succeed.
A fallback model would quietly change which model produced an eval number, which breaks rule 7's
"every number names its model".
**Supersedes.** —

## D-048 · The human writes the 20 synthetic session files; no in-repo generator · 2026-11-07 · human
**Decision.** The human writes each synthetic session's full event file
(`evals/data/sessions/synthetic/<id>.json`, `Session`-shaped) from the approved spec, ending in
their LeetCode-checked final code. There is no in-repo generator: T-018 is dropped. T-015, the
Anthropic adapter, is deferred until M7's model comparison needs Claude; its test assets stay
committed. T-017's checks stay, now validating the human's files. If an AI helps draft them, it is
Claude, never the model being evaluated (D-018), and the file's `meta.json` names it.
**Why.** The human: "i will generate the session events myself". Human-written sessions remove
generator bias at its source and make every snapshot the human's call. It also drops two tasks
and an LLM spend from M2.
**Supersedes.** D-017 (generation by an in-repo Claude generator); D-043's point 2 (the
generator writes the lead-up); D-046 (the generator's entry point).

## D-049 · Eval case interfaces the T-016 tests pin · 2026-11-07 · tester (the human asked to finish M2 without stopping)
**Decision.** The module is `tutor.evals.cases`.
- `Case` follows the §8.1 format, with no extra fields. `source` is `real` or `synthetic`, `session`
  carries exactly one of `capture_session_id` / `synthetic_path`, and `label_source` is
  `human_written`.
- `load_cases(suite, split, *, root=None, milestone=None)`:
  - reads `<root>/data/<suite>/<split>/cases.jsonl`; `root` is the evals directory;
  - an unknown suite or split is a `ValueError`;
  - a malformed or duplicate case is a `CaseError`;
  - the test split raises `SplitLockedError` unless `milestone` is listed in
    `<root>/test_approvals.json` as `{"approved": [...]}`, a file only the human writes.
- `load_case_session(case, *, settings, root=None)`:
  - a real case comes from `paths.eval_capture_db`, opened immutable;
  - a synthetic case comes from `synthetic_path`, relative to the repo root and confined to
    `evals/data/sessions/synthetic/`, and only if its `meta.json` says `"verdict": "accepted"`.
- Label fence: nothing under `src/tutor/` outside `tutor/evals/` mentions `evals/data` or imports
  `tutor.evals`, except `cli.py`, which wires `tutor-eval`.
**Why.** §8.1 and §8.2 give the formats and the guard but not the function names. The lock lives in
the loader, so no caller can forget it.
**Supersedes.** —

## D-050 · No label for "sorting"; a label table only if the list grows again · 2026-11-07 · human
**Decision.** Merge Sorted Array's final code copies and sorts. It gets **no algorithm label**: the
eval plan allows "up to 2", so zero is allowed, and no label in the list fits. No migration.
Deferred: replace the `session_algorithms.label` CHECK with an `algorithm_labels` table it
references (one migration), so that adding a label afterwards is a row insert, not a schema change.
**Why.** The human: "don't do another migration for the sort category". The label table removes
the recurring cost, but only pays off once a second label is needed.
**Supersedes.** —

## D-051 · Eval runner interfaces the T-022 tests pin · 2026-11-07 · tester (the human asked to finish M2 without stopping)
**Decision.** The module is `tutor.evals.runner`.
- `run(suite, split, *, predictor, settings, repeats=1, milestone=None, root=None,
  results_dir=None)` returns the §8.3 record and writes it to `<results>/<suite>/<run_id>.json`,
  plus a summary line, without per-case data, to `<results>/index.jsonl`. The test split is
  locked by `load_cases`, and a test run saves aggregates only (`cases: []`).
- `estimate(...)` counts cases and calls, prices them, and makes no calls.
- `summary_line(record)` names every version.
- A **predictor** is a callable `Session -> dict` with `.name` and `.version`. The runner hands it
  the `Session` only; graders see the case. `model` in the record is `name@version`.
- Aggregates are `accuracy`, `by_source.{real, synthetic}.{accuracy, n}`, `consistency` (the share
  of cases whose output is identical across repeats) and `errors`. An error counts as wrong, and is
  also counted separately (§6.4).
- `evals/graders/` (tester) holds the §8.4 `Grade` / `Grader`, `AlgorithmOverlap` (any overlap
  counts; an empty output scores 0) and `KeywordBaseline` (`keyword-v1`, the final code only).
  The runner imports them from the repo's `evals/` directory.
**Why.** §8.2 and §8.3 give the commands and the record but not the Python seam. A predictor
interface lets M3's LLM fields and the keyword baseline run through the same runner. The baseline
is tester-owned because it is the bar the model must beat.
**Supersedes.** — (architecture §2 put the keyword baseline in `fields/algorithm.py`; it now lives
with the graders)

## D-052 · Failure explanation is stored but not scored in M3 · 2026-11-07 · pm
The eval plan grades the explanation with an LLM judge, and rule 8 says no judge score counts until
the judge is calibrated (≥ 85%). The judge and the calibration work are M4's. M3 stores each
explanation in the result record and `analysis.db`, so M4 can grade the same outputs.
**Why.** A judge built in passing inside M3 would be uncalibrated, and its number couldn't count.

## D-053 · `tutor prompts lock` stays deferred · 2026-11-07 · pm
Its trigger ("M3 adds the field prompts") has arrived. M3 adds two prompts, so two hashes get
entered by hand, and the manifest contract test fails on any mismatch. The cost of a mistake is
one failed test.
**Why.** It's tooling that teaches nothing about harnesses or evals. New trigger: a hand-entered
hash causes a wrong commit, or there are more than 5 prompt versions.

## D-054 · Algorithm-field interfaces the T-024 tests pin · 2026-11-07 · tester
- `tutor.fields.algorithm.algorithm(session, *, client, settings, run_id, model=None) ->
  LLMResult[AlgorithmOutput]`, where `AlgorithmOutput.algorithms` holds 1–2 `AlgorithmLabel`s.
  It returns the whole `LLMResult`, not just the output, so the runner gets tokens and cost
  without a second path. The prompt version comes from `settings.prompts["algorithm"]`.
- The input is the final snapshot's code plus the problem title, difficulty and tags. It never
  includes the verdict, test counts, runs, errors or earlier snapshots (contract
  `test_algorithm_input.py`).
- `predictor_named(name, *, settings=None, client=None, model=None)`. An LLM predictor outputs
  `{"labels": [...]}` (the grader's shape) and exposes `.provider`, `.prompt_versions`,
  `.prompt_sha256` and `.last_usage`. The record's `model` is the model id; `summary_line` prints
  `prompt <name>-<version>, model <provider>:<model>` (rule 7). The keyword baseline keeps
  `name@version`.
- `tutor-eval run|estimate --model PROVIDER:MODEL`.
**Why.** §6.3 and §8.2 name the inputs and flags but not the Python seam, so the builder would
otherwise have to invent one.

## D-055 · Failure-rule interfaces, and the decider comes from the case · 2026-11-07 · tester
- `FailureType` in `models.py`. `fields/failure.py: failure_rule(status) -> FailureType | None`
  (passed → none, failed_too_slow → too_slow, else None).
- `evals/graders/failure_type_exact.py` (tester): exact match on `failure_type`; the explanation is
  ungraded until M4 (D-052).
- `predictor_named("failure_rules")` (`rules-v1`) applies the rules alone and raises for any other
  status. It measures the rule-decided half before the LLM exists. Output shape for the failure
  suite: `{"failure_type", "source", "explanation"}`.
- `aggregates.by_decider = {"rule": {accuracy, n}, "llm": {accuracy, n}}` for the failure suite.
  The split uses each **case's** `rule_decided` tag, never the output's `source`.
**Why.** §8.1 asks for accuracy split by decider, so the rules can't inflate the LLM's number. If
the split read the output, a model that labelled its own answers "rule" could move its cases into
the rule bucket.

## D-056 · Failure-field interfaces the T-026 tests pin · 2026-11-07 · tester
- `fields/failure.failure(session, *, client, settings, run_id, model=None) -> FailureResult(output:
  FailureOutput(failure_type, source, explanation), usage: Usage | None)`.
- **passed**: `none`, rule, explanation NULL, and no call. **failed_too_slow**: `too_slow` by rule,
  plus one call for the explanation only (§6.3: explanation is LLM unless passed); the model's type
  is discarded. **Every other status**: one call, `source: "llm"`.
- The model's type list leaves out `none`, because only Accepted is `none` and Accepted never
  reaches the model. A `none` answer is invalid and retried. not_submitted and unknown are named
  as such in the prompt.
- Input: `render(condense(session))` (rule 3) plus the verdict, test counts and error text (§6.3).
- `predictor_named("failure", ...)`: output `{failure_type, source, explanation}`, and
  `last_usage` is None when no call was made.
**Why.** §6.3 has the rule table but not the seam, and the too_slow case (rule type + LLM
explanation) is easy to get wrong in either direction.

## D-057 · `tutor analyze --llm` is opt-in · 2026-11-07 · tester
- `analyze(settings, *, run_id, since=None, llm=False, client=None, model=None)`;
  `AnalyzeReport.llm_errors`. CLI: `tutor analyze [--since] [--llm [--model PROVIDER:MODEL]]`.
- With `--llm`, the failure and algorithm fields run through the same functions the runner calls,
  writing `session_analysis`, `session_algorithms` and `field_provenance`. There is one provenance
  row per field that made a call: a passed session's failure field makes none, so it gets no row
  (its `call_id` is NOT NULL). Re-running replaces a session's rows.
- An LLM error in one field: logged as `llm_field_failed`; that field is left NULL or without rows; the run
  continues. A config error (e.g. an unpriced model) raises before anything is written.
**Why.** Without the flag, analyze stays offline and free, as in T-011. Spending money should be
asked for, not a side effect of refreshing facts. It refines T-027's Done-when ("`tutor analyze
[--model]`") with an explicit `--llm`.

## D-058 · The judges use gpt-5.5 for now · 2026-11-07 · pm
A judge of the same model family may favour its own outputs. A Claude judge would avoid that, but
the Anthropic adapter is deferred to M7 (D-048). Calibration (rule 8) measures the judge against
the human's grades either way: if gpt-5.5 agrees ≥ 85%, the self-preference worry is answered by
data. **Revisit** at M7, when the Anthropic adapter exists: re-measure the judge with a Claude
model on the same calibration set.

## D-059 · Timeline suite: outcome is a verdict string; no on-track algorithms · 2026-11-08 · test
The checklist's `outcome` is built by `evals/build/build_dataset.py` from the verdict, never typed:
`"<LeetCode verdict>, p/t tests passed"`, or `"not submitted"`. It is a fact (rule 1), so the
judge can check "names the final outcome" against data rather than a label. A string, not an
object, because the judge reads it as text. `story.on_track_algorithms` stays out of the
checklist: it says what would have worked, which a summary of what happened never needs (D-039).
The timeline cases reuse dev-v1's split (seeded draw, same rows), so no session changes split and
the failure / algorithm cases stay byte-identical; the new files start at `dev-v1` / `test-v1`.

## D-060 · Timeline field interfaces; length is measured, not enforced · 2026-11-08 · test
`tutor.fields.timeline`: `PROMPT = "timeline"`, `TimelineOutput(summary: str, non-empty)`,
`timeline(session, *, client, settings, run_id, model=None) -> LLMResult[TimelineOutput]`: one
structured call whose input contains `render(condense(session))` unchanged (rule 3). Runner:
`predictor_named("timeline")` → `{"summary"}`, `prompt_versions {"timeline": "v1"}`;
`graders_for("timeline")` → `[SentenceCount]` until the judge joins (T-033). `analyze --llm` writes
`session_analysis.timeline_summary` and a `timeline_summary` provenance row (prompt_name
`timeline`); no migration, 0001 already has both. **The 3–5 sentence length is asked for in the
prompt but not enforced by the schema**: a schema check would retry until the count fits and the
`at_most_5_sentences` metric would always read 1.00, hiding how often the model overruns. Code
counts sentences (`evals/graders/sentence_count.py`), so the judge never does arithmetic.

## D-061 · Judge graders in the runner: interface, cost, calibration file · 2026-11-08 · test
An `llm_judge` grader carries `field` (the `LLMClient` field: it routes the model through
`llm.fields.<field>` / `llm.default` and names the logged calls), `run_id` (set by the runner to
the record's, like a predictor) and `last_usage` (set by each `grade()`), and calls
`ctx.client.structured` inside `grade()`. `run(..., graders=None, judge_client=None)`: both default
(`graders_for(suite)`, `LLMClient(settings)`) and are injectable for tests. Each row gets
`judge_cost_usd`; `cost_usd_total` = predictor + judge, so a run's price is honest. A judge that
raises makes its row an error (`"judge: …"`), never a crashed run. `aggregates.by_metric =
{metric: {mean, n}}` over rows without an error, because a judge emits several checklist metrics
and `accuracy` reads only the first grade. `record["judge"]` names the first judge with its
provider/model and `calibrated`, which is true only when `evals/calibration.json` (`{"entries":
[{judge, version, agreement, n, decision}]}`, tester-owned, starts empty) lists that exact judge
version at agreement ≥ 0.85 (rule 8). A missing file means uncalibrated.

## D-062 · Timeline judge: five judged items, length by code, item-level agreement · 2026-11-08 · test
`evals/graders/timeline_judge.py` (`timeline-judge` v1, `prompts/judges/timeline/v1.md`) judges five
checklist items, each with a one-sentence reason before `met`: approaches, first approach (agrees
with the human's account; if off track, whether and roughly when they switched), no invented
correction, final approach and outcome, no invented events. "5 sentences or fewer" is counted by
code and the judge is never asked. "No invented correction" is left out of a case's score when the
person did switch approach, rather than counted as met, so it can't inflate the score or the
agreement. The judge reads the human's account (it is a grader; the field never sees labels) and the
rendered condensed timeline from a new `GradeContext.session`; the runner has to pass the case's
`Session` there and `graders_for("timeline")` returns the judge (a small builder step, tested in
`test_t033_timeline_judge.py`). Metric: `timeline_checklist` = share of applicable items met.
**Agreement** is item by item over the 20-summary calibration set, n/a items skipped. It is reported
with what an always-yes judge would score and how many of the human's "not met" items the judge
also caught, because a set where most items are met flatters a judge that always says yes.

## D-063 · "On track" means no pivot needed; syn-003 relabelled; judge must catch the misses · 2026-11-08 · human + test
**The human's definition** (from the T-033 calibration review): a first approach is **on the right
track** if it only needs bug fixes to pass; it is **off track** if passing needs a pivot to a different
algorithm, and too slow counts as not passing ("not meeting the performance constraints is wrong").
A **course correction** is a pivot to a different approach, whether or not the new one passes. This
is the rule `timeline/v2` must state (T-036) and the one the judge's "first approach" item applies.
**syn-003 relabelled** (rule 10, the human's reason): the per-start greedy scan that later swaps in a
smaller last element counts as a pivot at minute 8 to a second, still-wrong approach. Its story is now
2 approaches, `corrected: true, at_min: 8`; its failure type stays `wrong_approach`, so the spec
checker's rule becomes "wrong_approach ⇒ the first approach was off track" (a switch to another idea
that also fails is still wrong_approach). Only `timeline/dev` changes: **timeline dev-v2**; failure,
algorithm and timeline test cases are byte-identical and keep their versions. Calibration items 8 and
20 (that session) become first approach met, no invented correction n/a.
**Pass condition for a judge** (the human, 2026-11-08): agreement ≥ 0.85 item by item **and** it marks
not met at least 70% of the items the human marked not met (the human set "5 of 7"; after the relabel
the set has 5 not-met items, so 4 of 5). An always-yes judge would score 90/95 = 0.95 on this set, so
agreement alone can't pass a judge. The calibration set `evals/data/calibration/timeline/v1.jsonl` is
frozen by hash in `evals/data/manifest.json`.

## D-064 · timeline-judge v1 is calibrated · 2026-11-08 · test
On the human's 20 graded summaries (95 items), timeline-judge v1 on openai:gpt-5.5 agreed on every
item (1.00; an always-yes judge would score 0.95) and caught all 5 items the human marked not met,
so it passes D-063's condition and is recorded `accept` in `evals/calibration.json`. Caveats: one
run (repeat noise is measured at T-035); the set has only one kind of miss ("first approach"), so
the other four items are calibrated on "met" cases only; and the judge is the same model as the
field (D-058). **Revisit** when T-036 produces summaries with other kinds of mistakes, and at M7
with a Claude judge.

## D-065 · Failure-explanation judge interfaces · 2026-11-08 · test
- `evals.graders.failure_explanation_judge.FailureExplanationJudge`: name `failure-explanation-judge`,
  version `v1`, kind `llm_judge`, field `failure_explanation_judge`. Two items, `consistent` and
  `no_invented_cause`, each `{reason, met}`. Grades: `explanation_checklist` (share met), then
  `explanation.<item>`. A session with no explanation (passed) gets no grades.
- The judge's reference is the failure case's own `expected` (the human's failure type + key facts),
  not the timeline suite's story, so no dataset file changes. The condensed timeline comes from
  `ctx.session`, as for the timeline judge (D-062).
- Pass condition as D-063: agreement ≥ 0.85 item by item, and misses caught ≥ 70%.
**Why.** The eval plan's checklist for the explanation is exactly these two lines. Reusing the failure
case's labels keeps `dev-v1` frozen; key facts already say what failed.

## D-066 · Sort Colors relabelled: implementation_bug, first approach on track · 2026-11-08 · human
The real Sort Colors session (dev; failure-dev-003 / timeline-dev-003) was labelled `wrong_approach`,
first approach off track, never corrected. Calibrating the explanation judge showed the field blaming
an off-by-one in `while L < R` in 4 of 5 runs. The tester ran the final code on every 0/1/2 array up
to length 8: as written it is wrong on 4,033 of 9,840; with `L <= R` it is wrong on none. LeetCode's
constraint is n ≤ 300 (the human's screenshot), so the O(n²) idea passes. By the human's own
definition (D-063: on track = only bug fixes needed) the idea was on track.
New labels (the human's): failure type `implementation_bug` (it breaks ordinary inputs like `[1,0]`,
not a corner case); course correction `{on_track: true, corrected: null}`; `on_track_algorithms`
null; final approach names the `L < R` bug. Key facts and algorithms unchanged.
Effects: `failure/dev` → **dev-v2**, `timeline/dev` → **dev-v3** (every other cases file
byte-identical; test split untouched); T-020 label pin re-pinned in the T-029 test; timeline
calibration item cal-tl-03 `first_approach` → met (the summary called it on track), so that set has
4 misses, and timeline-judge v1 was re-measured (D-067). Baselines measured on failure dev-v1 /
timeline dev-v2 are re-measured at T-035.
**Why.** Rule 10: an expected label changes only with a written reason. Here the eval exposed a
wrong label, not a wrong output: the model was right and the label was not.

## D-067 · failure-explanation-judge v2 is calibrated; v1 rejected · 2026-11-08 · test
Calibration set: 20 explanations from stored M3 dev runs, 40 graded items, the human's grades (4 not
met, all on Sort Colors: three name the input `[2,0,1]`, which the timeline never shows; one says the
idea itself can't sort).
- **v1 @ openai:gpt-5.5: agreement 0.90 (n=40), misses caught 0/4**, the same as always-yes (0.90):
  rejected by D-063. Its reasons: it accepted an input worked out from an output, and read "the
  idea can't sort" as a bug.
- **v2** adds two general rules: a specific input/output/value counts only if written in the
  timeline; and the "could the idea work" line in both directions. **v2 @ openai:gpt-5.5: agreement
  1.00 (n=40), misses caught 4/4.** Run `20261108T214135Z-b3cedb3e`, $0.61.
- timeline-judge v1 re-measured on its updated set: **1.00 (n=95), misses caught 4/4**, run
  `20261108T213904Z-76a37ed6`, $0.63. Still calibrated.
**Caveat.** v2 was revised after seeing v1 miss these items and re-measured on the same 20, so 1.00
is optimistic, and all 4 misses come from one session. The rules are general (rule 9), but a fresh
hand-graded set from T-035's runs would show whether v2 generalises.
**Found:** `runner._is_calibrated` reads only `agreement`, so a judge entry with `decision: reject`
(like v1's 0.90) would count as calibrated. v1 is no longer used, but the runner should honour
`decision` and misses caught. Builder work, alongside wiring the judge into `graders_for("failure")`.

## D-068 · "Too slow" refined: a slow algorithm is off track, a slow implementation is not · 2026-11-08 · human
T-036's v2 applied D-063 literally ("too slow = off track") and called two sessions off track that
the human labelled on track: the right algorithm implemented wastefully (scanning a whole stack
instead of popping its top; slicing a string on every call instead of moving two indices). The
human's ruling: **off track** = passing needs a different algorithm or a technique the code lacks
(adding memoization / a DP table, a hash map, sorting, a window); **on track** = the algorithm is
right and the slowness comes from how it is implemented (an unneeded copy, using the chosen data
structure the wrong way). Adding a memo to plain recursion is a new technique, so that stays off
track (the existing label). Labels unchanged; `timeline/v3` states the refined rule.
**Why.** It keeps D-063's core ("only bug fixes needed") and the human's existing labels consistent.
