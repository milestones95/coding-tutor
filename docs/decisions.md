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
