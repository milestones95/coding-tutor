# Tracker — LeetCode Tutor Agent

> **The only place work status lives.** Owned by `/pm`. `/build` moves its own task to 🔄;
> only `/test` moves a task to ✅. Every status change gets a dated log line with evidence.

**Last reviewed:** —
**Active milestone:** M0
**Cost of one full dev eval run:** — *(fill in after the first run)*

Status: ⬜ Not started · 🔄 In progress · ⏸ Blocked (name who/what) · ✅ Done (by `/test` only)
Size: S (under an hour) · M (one session) · no L — split it

---

## Milestones

| # | Milestone | Status | Checkpoint |
|---|---|---|---|
| M0 | Foundation: capture in repo + submit fix, config, logging, LLM client (OpenAI), models, read-only loader | ⬜ | One captured session loads, validates, and one logged LLM call runs |
| M1 | Deterministic pieces: condenser, problem, time to finish, attempted at, **status** (D-014), `analysis.db` | ⬜ | Unit tests green on real + hand-built sessions; token budget measured |
| M2 | Dataset + eval runner: 30 cases (≈ 8 real + ≈ 22 Claude-generated, D-017), Anthropic adapter, split 20/10 | ⬜ | Runner writes a versioned result record for a trivial grader |
| M3 | Algorithm type, failure reason (status is no longer an LLM field) | ⬜ | Dev baseline recorded per field |
| M4 | Timeline summary + judge | ⬜ | Judge agreement ≥ 85% recorded |
| M5 | Progress Agent + `run_sql` | ⬜ | One fixture question answered with a logged trajectory |
| M6 | Part 2 evals | ⬜ | All five graders produce a baseline |
| M7 | Model comparison + test split | ⬜ | Comparison table below |

---

## Tasks — active milestone

| ID | Task | Owner | Size | Test assets | Status | Traces to |
|---|---|---|---|---|---|---|
Two tracks run side by side. **Capture** (T-002 → T-001) needs the human at the browser;
**Python** (T-003 → T-004, T-003 → T-005 → T-006 → T-007) does not. T-007 closes M0 and
needs T-004 and T-006; it does not need T-001 (it reads the frozen copy).

| ID | Task | Owner | Size | Test assets | Status | Traces to |
|---|---|---|---|---|---|---|
| T-002 | Move capture (extension + ingest server) into this repo | build | M | required | ✅ 2026-11-02 | D-015; D-011 |
| T-001 | Fix submit capture in the extension | build | M | required | 🔄 built; waits on human: reload + 3 submits (DW 3, 5) | eval-plan build order 1; D-014 |
| T-003 | Python project skeleton, config, JSON-lines logging, test harness | build | M | required | ✅ 2026-11-02 | arch §2, §11, §12, §13 |
| T-004 | Inference-side data models + read-only capture loader | build | M | required | ⬜ after T-003 | arch §4.1, §4.4; D-005, D-011, D-016 |
| T-005 | Prompt loader + manifest | build | S | required | ⬜ after T-003 | arch §7; rule 6 |
| T-006 | LLM client wrapper (`structured()`), OpenAI adapter, pricing, call log | build | M | required | ⏸ after T-005; human: confirm model id + enter prices | arch §6; rule 5; D-008, D-018 |
| T-007 | M0 checkpoint: load one session, make one logged call | build | S | required | ⬜ after T-004, T-006 | M0 checkpoint |

### T-002 · Move capture (extension + ingest server) into this repo
**Milestone:** M0 · **Size:** M · **Owner:** build
**Traces to:** D-015; D-011 (capture DB read-only to `src/tutor/`; path is config).
**Done when:**
1. `ux-extension/` holds only the capture code listed in D-015, plus the `package.json`,
   lockfile and `tsconfig.json` it needs. `server/src/agent/`, `server/src/mcp/` and the
   dashboard are gone. `ingest.ts` no longer imports them and runs no analysis on session end.
2. `npm install` then the ingest server's start command, both run from this repo, serve
   `localhost:7777`. The command is written in `ux-extension/README.md`.
3. Chrome loads the unpacked extension from this repo's `ux-extension/extension/`, and the
   old unpacked copy is removed from Chrome (the human does this and confirms in the log).
4. The server writes `data/capture.db` in this repo. It is seeded by an SQLite `.backup`
   of `leetcode-analyzer/data/leetcode.db` taken with the old server stopped. Row counts per
   table match the source, the old file is left untouched, and the query is saved in
   `scripts/discovery/`.
5. One real Run event arrives in `data/capture.db` after the move (read-only query).
6. `.gitignore` covers `node_modules/` and `logs/` and still ignores `data/`, but not
   `docs/data/` (`/data/`). Because `ux-extension/data/` is no longer used, that is enough.
7. Node is pinned: `ux-extension/.nvmrc` = `20.19.5` and `package.json`
   `"engines": {"node": ">=20.19.5 <21"}` (architecture §2).
**Not included:** the submit fix (T-001); any change to what capture records; the loader
(`src/tutor/capture/`); keeping the old analyzer, MCP or dashboard working.
**Test assets:** required. `/test write T-002` writes the row-count check and the
Run-event check.
**Log**
- 2026-11-02 `/pm idea` — added by the human's decision (D-015). Gate: plumbing, not
  harness or eval learning, but it blocks T-001 and the loader's live-DB path. It delays
  M0 by about one session. Scope warning: M0 has two capture tasks and no harness work yet.
- 2026-11-02 `/test write T-002`. Written: `tests/contract/test_capture_fence.py` (5 tests,
  capture fence §4.3 #5); `tests/acceptance/test_t002_capture_move.py` (20 tests: Done-when 1, 2,
  4, 6, 7; 4 of them `live_capture`, skipped by default); `tests/acceptance/conftest.py`
  (`live_capture` gate); `evals/fixtures/capture/run_check_success.json` (hand-built Run
  response) + README. Conventions agreed with the human: the server starts with
  `npm --prefix ux-extension start`, and seeding writes `data/capture.seed.json`
  (`source_path`, `source_sha256` of db + wal, `seeded_at`, `row_counts`). The count query
  goes in `scripts/discovery/16_capture_seed_counts.sql`. Run with
  `uv run --no-project --with pytest pytest tests/contract/test_capture_fence.py tests/acceptance/test_t002_capture_move.py`
  (plain `uv run pytest` once T-003 lands). Result: 13 failed + 2 errors (server fixture: no
  `node_modules`), all for the right reason. 8 pass already as guards (`.env`/`data/` ignored,
  no Python reaches into `ux-extension/`); 4 skipped. The two server-probe tests can't be
  exercised until the build exists. Done-when 3 stays a human confirmation in this log.
- 2026-11-02 `/build` → 🔄. Removed `server/src/agent/`, `mcp/`, `dashboard.*` and `diff.ts`.
  `ingest.ts` has no analyzer queue and no dashboard routes. `db.ts`: `endSession` no longer
  sets `analysis_status`, `markAccepted` no longer deletes `attempts` rows, and the
  attempt-writing helpers are gone (D-021). `config.ts`: only `PORT` / `LCA_DB` (default
  `<repo>/data/capture.db`) / `LCA_IDLE_MINUTES`, no `.env`. The popup's dashboard buttons
  and Analysis row were removed (they pointed at the deleted dashboard). Added
  `package.json` (start/typecheck/test/seed:problems, engines), lockfile, `tsconfig.json`,
  `.nvmrc`, README. `.gitignore` → `/data/`, `logs/`, `node_modules/`, Python caches.
  **Seeded** `data/capture.db` with `scripts/seed_capture_db.py` (rehearsed on a scratch copy
  first): 4091 problems, 38 sessions, 971 snapshots, 33 judge events, 13 attempts, 22 gaps.
  The source `.db` and `-wal` are unchanged (hash 01d45f73…). Tests: Python suite 62 passed,
  4 skipped; capture unit tests 4/4 (`npm --prefix ux-extension test`); typecheck clean;
  `-m live_capture`: 3 passed, 1 failed = Done-when 5, waiting for a real Run.
  **Waiting on the human:** load the unpacked extension from `ux-extension/extension`, remove
  the old one (Done-when 3), start the server, click Run once (Done-when 5).
- 2026-11-02 Human: duplicate-zeros session at 04:12–04:20Z captured by the new server
  (41 snapshots, 5 Runs; Submit missing, which is the T-001 bug). **Done-when 3 confirmed by the
  human:** Chrome has the unpacked extension from `ux-extension/extension` loaded (renamed
  "LeetCode Tutor Agent" in `manifest.json` to tell it apart), not the old copy.
- 2026-11-02 `/test run` → ✅. Commit f8d38d7; no judging files in the builder's diff. Capture
  fence 5/5; T-002 acceptance 18 passed + 4 `live_capture` passed (row superset, old DB hash
  unchanged, seed counts, Run after seeding); capture unit 4/4; `tsc --noEmit` clean.
  Done-when 1–7 met. Scope: the popup edits and the `db.ts` write changes follow from removing
  the analyzer (D-021); not creep. Uncommitted: the human's `manifest.json` name change.

### T-001 · Fix submit capture in the extension
**Milestone:** M0 · **Size:** M · **Owner:** build, in this repo's `ux-extension/` (D-015) · **Depends on:** T-002
**Traces to:** `eval-plan.md` build order step 1 — "save the LeetCode verdict at capture
time"; D-014 (status is the verdict); `architecture.md` §4.4 (loader expects submit rows).
**Problem:** 0 of 24 captured judge events are submits; all `submission_id`s are
`runcode_…` (`scripts/discovery/10_submit_timing.sql`). The extension's hook
(`page-hook.js`) sees LeetCode's `/submissions/detail/<id>/check/` polls, but submits
(numeric IDs) are never written.
**Done when:**
1. A written finding names where submits are dropped in the extension (file + line).
2. On a real Submit, the extension writes exactly one `judge_events` row with
   `kind='submit'`, numeric `submission_id`, `ts` = result arrival, `status` = LeetCode's
   verdict text, `tests_passed`, `tests_total`, and `error_detail` for failures. Only the
   final poll (`state = SUCCESS`) is recorded; repeat polls don't create duplicates.
3. Verified by three deliberate submits — Accepted, Wrong Answer, Time Limit Exceeded —
   each checked with a read-only query saved in `scripts/discovery/`.
4. No LeetCode user profile data (`user` block) is stored.
5. `capture.submits_reliable_since` value proposed for `tutor.toml` (the human sets it;
   it lands in the file once T-003 creates it).
**Not included:** capturing GraphQL `submissionDetails` (submitted code, raw `statusCode`)
— a possible follow-up via `/pm idea`; backfilling old submissions from LeetCode history;
moving the extension into this repo (that is T-002); any change to this repo's loader.
**Test assets:** required — `/test write T-001` writes the acceptance query and expected
row shape before the fix.
**Log**
- 2026-11-02 `/pm idea` — added. Gate: capture work (not harness/eval learning), but it is
  eval-plan build-order step 1 and every real session's status depends on it under D-014.
  Displaces nothing yet; delays M0 by ~1 session. Blocked until the human gives the
  extension's source location.
- 2026-11-02 investigation (read-only) — Source: `/Users/milestucker/dev_work/leetcode-analyzer`
  (running copy; `ux-extension/` here is byte-identical). Findings so far:
  (a) on paper the whole path handles submits — `page-hook.js` matches numeric `check/` IDs,
  `judge.ts` classifies them as `submit`, `ingest.ts` inserts them;
  (b) the live DB still has 0 submit rows after ~9 resubmits on 2026-11-02, while snapshots from
  the same tabs arrived. Two traced cases: coin-change submissions at 22:30:33Z and 22:51:38Z
  (LeetCode timestamps) left no judge event; the second was followed by a new session only at
  22:53:09Z (`scripts/discovery/13_live_submits.sql`, `14_live_today.sql`, `15_live_latest.sql`).
  [Corrected: an earlier note said ~21:30Z — wrong timezone conversion.]
  (c) replaying an Accepted submit event through `Ingest.handle` against a scratch copy stores it
  correctly (kind=submit, 191/191, end_reason=accepted).
  ⇒ The event is lost in the browser, between LeetCode's response and the background worker.
  (d) The final submit `check/` response has `state: SUCCESS`, numeric `submission_id`,
  `task_name: judger.judgetask.Judge` — `judge.ts` would classify it as a submit. No `[LCA]`
  console warnings on submit, so the message likely never reached `relay.js`.
  (e) `page-hook.js:68` swallows every error after the response (`.catch(() => {})`), so a
  failure there is invisible. Leading hypothesis (unconfirmed): `readCode()` (`page-hook.js:17-21`)
  throws on a disposed Monaco model while LeetCode switches to the submission view, so the
  judge message is never posted. Next: human runs a one-line Monaco-model check after a submit.
  (f) Monaco check: two healthy, non-disposed models — hypothesis (e) **rejected**.
- 2026-11-02 **Finding (done-when 1 met):** submits poll a different URL than runs —
  Submit `/submissions/detail/<numeric>/v2/check/`, Run `/submissions/detail/runcode_…/check/`
  (human's DevTools Network tab, submission 2188140749, Accepted 191/191). `page-hook.js:53`
  `CHECK_URL = /\/submissions\/detail\/[^/]+\/check\/?/` does not match the `/v2/` segment,
  so every submit poll is skipped before parsing (regex tested against both URLs: submit
  `false`, run `true`). Secondary: `server/src/judge.ts:59` URL fallback for `submission_id`
  has the same blind spot (body field is used first, so not triggered today).
  Status → ⬜ ready for `/test write T-001`.
- 2026-11-02 `/test write T-001`. Fixtures (`evals/fixtures/capture/`): Accepted and OLE submit
  responses **transcribed** from the human's screenshots, a RUNNING_TESTS poll (screenshot);
  **hand-built** WA, TLE, PENDING, and an Accepted response with a SENTINEL `user` block.
  Provenance is in the README. Contract `tests/contract/capture/submit_capture.test.ts` (20):
  `page-hook.js` loaded unchanged in `node:vm` with stubbed fetch/monaco/postMessage, plus
  `normalizeJudge`. **Agreed with the human:** the result must still be posted when reading the
  editor throws (code = null). Acceptance `tests/acceptance/test_t001_submit_capture.py` (8: Done-
  when 2 and 4 on the real server with a temp DB; Done-when 3 `live_capture` via the new
  `scripts/discovery/17_t001_submit_rows.sql`). Result: contract 8 fail for the right reason
  (6 × `/v2/` not matched, 1 × editor error drops the result, 1 × `judge.ts` URL fallback),
  12 pass as guards. Acceptance: 6 pass as guards (the server already stores submits),
  **1 fails: a new defect.** A repeated final poll of an Accepted submit opens a phantom session
  holding a second copy (the Accepted ended the first session). Live: fails until the human
  submits. Builder must also add the `test:contract` script (architecture §12); until then
  run `cd ux-extension && npx tsx --test ../tests/contract/capture/*.test.ts`.
- 2026-11-02 `/build` → 🔄. `page-hook.js`: `CHECK_URL` accepts an optional `v<digits>/` segment
  (Submit polls `/v2/check/`); the code read is wrapped so an editor error posts the result with
  `code = null` and doesn't drop it. `judge.ts`: the same optional segment in the
  `submission_id` URL fallback. `ingest.ts` / `db.ts`: before a session is chosen, a result
  whose `submission_id` is already stored for that problem is ignored (`sessionWithJudgeEvent`
  replaces the per-session `hasJudgeEvent`), so a repeated Accepted can't open a phantom
  session (D-023). `package.json`: `test:contract`. Unit tests: 4 added (8 total). Results:
  capture contract 20/20, capture unit 8/8, `tsc` clean, `uv run pytest` 69 passed, 5 skipped
  (`live_capture`). No judging files edited. **Waiting on the human:** restart the ingest server,
  reload the extension and the LeetCode tab, make the 3 deliberate submits (Done-when 3);
  then propose `capture.submits_reliable_since` (Done-when 5).

### T-003 · Python project skeleton, config, JSON-lines logging, test harness
**Milestone:** M0 · **Size:** M · **Owner:** build
**Traces to:** architecture §2 (directory map), §11 (config), §12 (test layout), §13 (logs).
**Done when:**
1. `pyproject.toml` (uv, Python 3.13, pydantic v2, python-dotenv, pytest) with console
   scripts `tutor` and `tutor-eval` that print help. `uv sync` and `uv run pytest` succeed
   on a clean checkout.
2. `tutor.toml` holds every §11 key with its default. `config.py` loads it into a frozen
   `Settings`, where `TUTOR__SECTION__KEY` env vars override any key. Secrets are read only
   from env/`.env`. An unknown key in `tutor.toml` raises.
3. `tests/conftest.py`: the default run is `-m "not llm"`, and a network-blocking fixture
   makes any unmarked provider call fail.
4. A JSON-lines log helper writes `logs/pipeline.jsonl` (one object per line, `ts`,
   `run_id`, `event`, plus fields). `logs/` is gitignored (T-002 does the file edit).
**Not included:** models, loader, LLM client, migrations, any CLI subcommand beyond help.
**Test assets:** required. `/test write T-003` covers config precedence, the secrets-only-
from-env rule, the unknown-key error, and the network block.
**Log**
- 2026-11-02 `/test write T-003`. **Ownership change:** Done-when 3 (`tests/conftest.py`: network
  block, default `-m "not llm"`, `llm` marker) is test infrastructure that judges the builder,
  so the tester wrote it (rule 11). The builder must not edit it. Interfaces agreed with the
  human: `tutor.config.load_settings(toml_path=None, env=None, dotenv_path=None) -> Settings`
  (frozen, attribute access, no secret fields), `tutor.config.ConfigError` (names the key),
  `tutor.logs.new_run_id()`, `tutor.logs.log_event(event, *, run_id, path=None, **fields)`
  (default `<paths.logs>/pipeline.jsonl`). Written: `tests/conftest.py`;
  `tests/contract/test_network_block.py` (6, **pass**); `tests/contract/test_config_secrets.py`
  (5); `tests/acceptance/test_t003_skeleton.py` (14, Done-when 1, 2, 4). Result: 19 fail for
  the right reason (no `pyproject.toml`, no `tutor.toml`, no `tutor` package, no console
  scripts); the 6 harness tests pass. Whole `tests/` tree: 14 passed, 32 failed, 2 errors,
  4 skipped (T-002 + T-003 combined; T-002's localhost server probe is not blocked).
- 2026-11-02 `/build` → 🔄. `pyproject.toml` (hatchling, src layout, Python ≥ 3.13, pydantic ≥ 2.7,
  python-dotenv, pytest dev group) + `uv.lock`; `tutor.toml` with the §11 defaults;
  `src/tutor/config.py` (frozen pydantic sections with `extra="forbid"`, no in-code defaults,
  errors name the key and never the value); `src/tutor/logs.py`; `src/tutor/cli.py`
  (argparse, help only). Unit tests: `tests/unit/test_config.py` (9), `tests/unit/test_logs.py` (4).
  `uv run pytest`: 62 passed, 4 skipped (`live_capture`). No judging files edited.
- 2026-11-02 `/test run` → ✅. Commit f8d38d7; no judging files in the builder's diff.
  Contract 16/16; acceptance 32 passed + 4 `live_capture` skipped (those 4 pass with
  `-m live_capture`); Python unit 14/14; capture unit 4/4; `tsc --noEmit` clean. **Gate not
  run:** Python lint/types — none configured (the architecture names none). Fresh clone of the
  branch: after `uv sync` alone, all T-003 and contract tests pass. The 3 problems are T-002 Node
  tests that need `npm --prefix ux-extension install` (2 errors + 1 failure, each with that
  message); after it, 62 passed, 4 skipped. **Finding for `/pm`:** Done-when 1 says "`uv sync` and
  `uv run pytest` on a clean checkout", but the repo now needs both installs. The wording
  should name both. Not a build defect.

### T-004 · Inference-side data models + read-only capture loader
**Milestone:** M0 · **Size:** M · **Owner:** build
**Traces to:** architecture §4.1 (models: `Session`, `Snapshot`, `RunEvent`, `SubmitEvent`,
`Problem`), §4.4 (loader rules); D-005, D-011, D-016.
**Done when:**
1. `models.py` holds the §4.1 inference-side models: frozen, typed and validated.
2. `capture/loader.py` opens a capture DB read-only, with the path and mode given by the
   caller. `immutable=1` on `paths.capture_db` raises. It never writes, and never reads
   `attempts*` or `sessions.analysis_*`.
3. On the frozen copy (`data/reference/capture.db`), `iter_sessions()` yields exactly the 8
   real sessions and logs the 14 non-attempts as excluded, each with its reason, to
   `pipeline.jsonl`.
4. `verdicts.csv` rows become `SubmitEvent(ts=None, source="human_resubmit")`. A conflicting
   captured verdict raises `VerdictConflict`, and `EXCLUDE` rows mark non-attempts.
5. A bad timestamp raises `CaptureFormatError` naming the session and row.
**Not included:** `CondensedSession`, `Moment` and `SessionAnalysis` (M1); status mapping
(M1); synthetic-session loading (M2).
**Test assets:** required. `/test write T-004` covers loader contract tests on tiny SQL
fixtures, the extension-analysis fence (§4.3 #3), and an acceptance check of 8 kept / 14
excluded on the frozen copy.

### T-005 · Prompt loader + manifest
**Milestone:** M0 · **Size:** S · **Owner:** build
**Traces to:** architecture §7; rule 6.
**Done when:** `load_prompt(name, version)` returns a `LoadedPrompt` (text, sha256,
declared variables) from `prompts/<name>/v<N>.md` front matter. `substitute` raises on a
missing or extra variable. `prompts/manifest.json` records each file's sha256, and
`tutor prompts check` fails when a file no longer matches it.
**Not included:** any field prompt; the agent system-prompt builder (M5).
**Test assets:** required. `/test write T-005` adds the manifest-hash contract test and the
templating errors.

### T-006 · LLM client wrapper (`structured()`), OpenAI adapter, pricing, call log
**Milestone:** M0 · **Size:** M · **Owner:** build
**Traces to:** architecture §6.1, §6.4, §6.5; rule 5; D-008 as amended by D-018.
**Done when:**
1. `LLMClient.structured()` works per §6.1, always validating the output with pydantic.
   The model comes from config, and a `--model` override is honoured.
2. `adapters/openai.py` uses OpenAI's native structured output. Nothing outside
   `tutor/llm/` imports a provider SDK (SDK fence, §4.3 #2).
3. The retry and error table in §6.4 is implemented and unit-tested with `FakeAdapter`.
   A missing key, unknown model or missing price raises `LLMConfigError` before any call.
4. Every attempt writes one `logs/llm_calls.jsonl` line with all §6.5 fields. Bodies go to
   `logs/llm_bodies/<call_id>.json`, and cost comes from `config/pricing.toml`.
**Not included:** `chat()` and tool calls (M5); Anthropic adapter (M2); Gemini adapter (M7).
**Blocked on the human:** (a) confirm the OpenAI model id (`gpt-5.5` was taken from the old
repo); (b) enter its prices and `as_of` date in `config/pricing.toml`.
**Test assets:** required. `/test write T-006` covers the SDK-fence contract test, the
log-line schema, the retry table, and config errors.

### T-007 · M0 checkpoint: load one session, make one logged call
**Milestone:** M0 · **Size:** S · **Owner:** build
**Traces to:** M0 checkpoint.
**Done when:** `tutor smoke --session <id>` loads one real session from the frozen copy,
validates it, and makes one `structured()` call through the wrapper with a throwaway
prompt `prompts/smoke/v1.md` (returning `{problem_slug}` from the problem title). One
complete line appears in `llm_calls.jsonl` with a non-zero `cost_usd`.
**Not included:** any real field; the smoke prompt is never used by a field.
**Test assets:** required. `/test write T-007` writes an acceptance test marked `llm` that
checks the log line and the validated output.

## Next milestone — M1 (planned, not started)

Starts when M0 is ✅. IDs are reserved; detail is final but may be re-sized at the M0 review.

| ID | Task | Owner | Size | Test assets | Traces to |
|---|---|---|---|---|---|
| T-008 | `analysis.db` migrations: `0001_init.sql` + `migrate.py` (refuses the capture path) | build | M | required | arch §3.2–3.3 |
| T-009 | Condenser `c1`: `condense` / `render` / `change_summary`, `CondensedSession`, `Moment`, budget truncation | build | M | required | arch §5; eval-plan condensing tests; D-006, D-013 |
| T-010 | Deterministic fields: problem, time to finish, attempted at (UTC + local date), status table + `status_source` | build | M | required | arch §4.3, §5.1; D-014, D-019, D-020 |
| T-011 | Deterministic pipeline: `tutor analyze` writes `sessions` + `condensed_timelines`; `tutor rebuild-timelines`; `tutor check` | build | M | required | arch §5.6, §13; D-012 |
| T-012 | M1 checkpoint: all unit/contract tests green on the 8 real + hand-built sessions; token budget measured (max / median est. tokens recorded here) | test | S | required | M1 checkpoint; eval-plan condensing tests |

**Later milestones (one line each until M1 closes):** M2: specs + Claude generator
+ review loop, Anthropic adapter, dataset split, runner and result record with real/synthetic
breakdown. M3: algorithm and failure-reason fields with dev baselines. M4: timeline +
judge calibration. M5: fixture DB, `chat()`, loop, `run_sql`. M6: five Part 2 graders.
M7: Gemini adapter, model comparison, first test-split run.

---

## Eval baselines (dev)

Every number names its versions. Noise band = spread across 3 runs of the same version.
Each metric is also recorded real-only and synthetic-only in its result record (D-018).
Status accuracy is not an eval any more: status is code (D-014), covered by T-010's tests.

| Metric | Value | Noise band | Prompt | Model | Dataset | Judge | Date |
|---|---|---|---|---|---|---|---|
| failure type accuracy (LLM-decided) | | | | | dev-v1 | — | |
| failure type accuracy (rule-decided) | | | — | — | dev-v1 | — | |
| algorithm accuracy | | | | | dev-v1 | — | |
| algorithm — keyword baseline | | | — | — | dev-v1 | — | |
| failure explanation (judge) | | | | | dev-v1 | | |
| timeline checklist (judge) | | | | | dev-v1 | | |
| agent exact answers | | | | | fixture-v1 | — | |
| agent pattern recall (judge) | | | | | fixture-v1 | | |
| agent grounding | | | | | fixture-v1 | — | |

## Judge calibration

| Judge | Version | Agreement with hand labels | n | Date |
|---|---|---|---|---|

## Test-split log

Run only via `/test milestone`. Aggregates only.

| Date | Milestone | Metric | Dev | Test | Gap |
|---|---|---|---|---|---|

## Model comparison

| Model | Accuracy (per field) | Cost / session | Latency | Consistency (3 runs) |
|---|---|---|---|---|

---

## Deferred — not scheduled

Every item has a trigger: the condition that would make it worth doing.

| Idea | Why not now | Trigger |
|---|---|---|
| "Expected approach" with code snippet | Out of scope in eval plan | Plan revised to include it |
| Running code via LeetCode API | Out of scope; verdict already comes from capture | — |
| Per-session planning / coding / debugging minutes | Open question in eval plan | After M6, if aggregate questions fail for lack of data |
| Dashboard / UI | Out of scope (UI polish) | Never, for this project's goal |

## Dropped

| Idea | Why | Date |
|---|---|---|

---

## Session log

| Date | Completed | Started | Added | Notes |
|---|---|---|---|---|
| 2026-11-02 | — | — | T-001, T-002 | `/pm idea`: submit capture fix added to M0 (eval-plan build order 1). T-001 finding written (`/v2/check/` regex miss). T-002 added (D-015, capture moves here; capture only). `/pm plan` not yet run. |
| 2026-11-02 | — | — | T-003 – T-007 (M0); T-008 – T-012 reserved (M1) | `/pm plan` (first plan). M0 = 7 tasks, 2 of them capture. Baselines table: status rows removed (D-014). |
