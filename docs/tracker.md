# Tracker — LeetCode Tutor Agent

> **The only place work status lives.** Owned by `/pm`. `/build` moves its own task to 🔄;
> only `/test` moves a task to ✅. Every status change gets a dated log line with evidence.

**Last reviewed:** 2026-11-03 (`/pm review`, M1 close)
**Active milestone:** M2 (planned 2026-11-07)
**Cost of one full dev eval run:** — *(fill in after the first run)*

Status: ⬜ Not started · 🔄 In progress · ⏸ Blocked (name who/what) · ✅ Done (by `/test` only)
Size: S (under an hour) · M (one session) · no L — split it

---

## Milestones

| # | Milestone | Status | Checkpoint |
|---|---|---|---|
| M0 | Foundation: capture in repo + submit fix, config, logging, LLM client (OpenAI), models, read-only loader | ✅ 2026-11-03 (T-007) | One captured session loads, validates, and one logged LLM call runs |
| M1 | Deterministic pieces: condenser, problem, time to finish, attempted at, **status** (D-014), `analysis.db` | ✅ 2026-11-03 (T-012) | Unit tests green on real + hand-built sessions; token budget measured |
| M2 | Dataset + eval runner: 28 cases (8 real + 20 synthetic, D-045), Anthropic adapter, generator, split | ⬜ | Runner writes a versioned result record for a trivial grader |
| M3 | Algorithm type, failure reason (status is no longer an LLM field) | ⬜ | Dev baseline recorded per field |
| M4 | Timeline summary + judge | ⬜ | Judge agreement ≥ 85% recorded |
| M5 | Progress Agent + `run_sql` | ⏸ Part 2, after Part 1 (2026-11-03) | One fixture question answered with a logged trajectory |
| M6 | Part 2 evals | ⏸ Part 2, after Part 1 (2026-11-03) | All five graders produce a baseline |
| M7 | Model comparison + test split — **Part 1 only** for now | ⬜ | Comparison table below |

---

## Tasks — M0 (✅ done 2026-11-03)

| ID | Task | Owner | Size | Test assets | Status | Traces to |
|---|---|---|---|---|---|---|
Two tracks run side by side. **Capture** (T-002 → T-001) needs the human at the browser;
**Python** (T-003 → T-004, T-003 → T-005 → T-006 → T-007) does not. T-007 closes M0 and
needs T-004 and T-006; it does not need T-001 (it reads the frozen copy).

| ID | Task | Owner | Size | Test assets | Status | Traces to |
|---|---|---|---|---|---|---|
| T-002 | Move capture (extension + ingest server) into this repo | build | M | required | ✅ 2026-11-02 | D-015; D-011 |
| T-001 | Fix submit capture in the extension | build | M | required | ✅ 2026-11-03 `/test run` | eval-plan build order 1; D-014 |
| T-003 | Python project skeleton, config, JSON-lines logging, test harness | build | M | required | ✅ 2026-11-02 | arch §2, §11, §12, §13 |
| T-004 | Inference-side data models + read-only capture loader | build | M | required | ✅ 2026-11-03 `/test run` | arch §4.1, §4.4; D-005, D-011, D-016 |
| T-005 | Prompt loader + manifest | build | S | required | ✅ 2026-11-03 `/test run` | arch §7; rule 6 |
| T-006 | LLM client wrapper (`structured()`), OpenAI adapter, pricing, call log | build | M | required | ✅ 2026-11-03 `/test run` | arch §6; rule 5; D-008, D-018 |
| T-007 | M0 checkpoint: load one session, make one logged call | build | S | required | ✅ 2026-11-03 `/test run` | M0 checkpoint |

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
- 2026-11-03 live verification (human at the browser, server restarted 12:09:52Z with the fix).
  `17_t001_submit_rows.sql` on the live DB: 7 submits, each stored once with a numeric id —
  Time Limit Exceeded 259/286, Output Limit Exceeded 260/286, Accepted ×2 (min-cost-climbing-stairs);
  Accepted 72/72, Wrong Answer 55/72 ×2 with distinct ids (contains-duplicate-ii). Failures carry
  `error_detail`, Accepted don't; each Accepted ended its session. `pytest -m live_capture`
  `test_dw3_three_deliberate_submits_were_captured`: 1 passed (Done-when 3).
  **Done-when 5 — human confirmed:** `capture.submits_reliable_since = 2026-11-04`. The fix went live
  mid-day 2026-11-03 and the setting holds a date, so the next full day is used; setting it to
  2026-11-03 would label the 04:12Z duplicate-zeros session (submitted, not captured) as
  not_submitted. Not yet written to `tutor.toml`: `test_t003_skeleton.py` asserts it is unset, so
  writing it needs `/test write` to update that expectation (reason: human set the value per T-001
  DW 5). For `/pm`. Status: ready for `/test run`.
- 2026-11-03 `/test run` → **✅ PASS.** Build diff (a244c08..69e7848) touches no judging files.
  Capture contract 20/20, capture unit 8/8, `tsc` clean, `uv run pytest` 69 passed / 5 skipped
  (`live_capture`, run separately: 5 passed against the live DB). Done-when 1–5 met (finding at
  `page-hook.js:53`; DW 2/4 acceptance on a temp-DB server; DW 3 live, 7 real submits incl. Accepted,
  WA, TLE, OLE; no `user` block stored; DW 5 human set 2026-11-04). Not run: Python lint/type
  check (none configured in `pyproject.toml`), grader tests (none exist yet), evals (no LLM field
  touched). Out of scope, not the builder's: the human's uncommitted `manifest.json` rename.

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
**Log**
- 2026-11-03 `/test write T-004`. Interfaces and edge rules agreed with the human: D-024
  (verdict is verbatim text; reliable-since compared in New York time; captured submit wins
  over an agreeing CSV row, a disagreement raises; CSV matches by session id only).
  Shared builder `tests/_capture_fixture.py` (capture DDL as frozen, optional analyzer tables
  with a sentinel). Acceptance `tests/acceptance/test_t004_loader.py` (26 + 1 `live_capture`:
  DW 1 models, DW 2 modes / sorting / since / live-path refusal / analyzer sentinel / session-id
  matching / reliable-since timezone, DW 3 exclusion reasons, DW 4 CSV rules, DW 5 timestamps;
  the frozen-copy check expects the 8 ids in verdicts.csv and 14 exclusions). Contract
  `test_capture_loader_readonly.py` (5: file unchanged, missing file not created, `ro` sees WAL
  rows) and `test_extension_analysis_fence.py` (2, with its own grading test). Result: all
  T-004 tests fail for the right reason (`tutor.models` / `tutor.capture` missing); the fence
  passes. Note for the architecture: "no test reads `data/`" (§12) vs this task's frozen-copy
  check, which is `live_capture` like T-001's.
- 2026-11-03 `/build` → 🔄. `src/tutor/models.py` (§4.1 models + `Verdict`; frozen, `extra=forbid`,
  timestamps must be aware and are normalised to UTC; `events` discriminated by `kind`).
  `src/tutor/capture/loader.py`: `CaptureLoader` opens a SQLite URI (`mode=ro`, or
  `mode=ro&immutable=1`), selects named columns from sessions / snapshots / judge_events /
  problems only, merges verdicts.csv per D-024, logs `session_excluded`. Rows the models can't
  take (missing problem, NULL language or difficulty, unknown kind) raise `CaptureFormatError`
  naming the session (D-025). Unit tests: 13 (`tests/unit/test_loader_internals.py`). Results:
  T-004 acceptance 26/26 + frozen copy 1/1 (`live_capture`: 8 kept, 14 excluded, file
  unchanged), contract read-only 5/5, fences 7/7. No judging files edited.
- 2026-11-03 `/test run` → **✅ PASS.** Build diff (77863fc..b4b6869) touches no judging files.
  T-004 acceptance 26/26 + frozen copy 1/1 (`live_capture`), contract 26/26 (whole dir),
  builder unit 13. Done-when 1–5 met. Not run: Python lint/type check (none configured),
  grader tests (none exist), evals (no LLM field).

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
**Log**
- 2026-11-03 `/test write T-005`. Interfaces: D-024 items 6–7. Acceptance
  `tests/acceptance/test_t005_prompts.py` (17: fields, `$$` escape, missing/extra variables,
  missing file, front matter vs path and body, `tutor prompts check` pass / edited / unlisted /
  gone / no manifest). Contract `test_prompt_manifest.py` (3, on the real `prompts/`). Result:
  all fail for the right reason (`tutor.prompts` and the `prompts` subcommand missing,
  `prompts/manifest.json` missing) except the naming check, which passes on an empty tree.
  For `/pm`: nothing says how a manifest entry is written for a new prompt (`tutor prompts
  lock`?); the tests write their own manifests, so this doesn't block T-005.
- 2026-11-03 `/build` → 🔄. `src/tutor/prompts.py`: `load_prompt`, `LoadedPrompt.substitute`,
  `PromptError`, `check_manifest`; front matter read by a small flat `key: value` / `key: [a, b]`
  parser, no YAML dependency (D-025). `tutor prompts check [--root]` in `cli.py`.
  `prompts/manifest.json` = `{}` (no prompts yet). Unit tests: 9
  (`tests/unit/test_prompts_internals.py`). Results: T-005 acceptance 17/17, contract manifest
  3/3, `tutor prompts check` exit 0 on the repo. Whole suite: `uv run pytest` 142 passed,
  6 skipped; `-m live_capture` 6 passed; capture contract 20/20, unit 8/8, `tsc` clean.
- 2026-11-03 `/test run` → **✅ PASS.** Same diff, no judging files. T-005 acceptance 17/17,
  contract manifest 3/3, builder unit 9, `tutor prompts check` exit 0. Done-when met. Whole
  suite 142 passed / 6 skipped, `live_capture` 6/6, capture contract 20/20, capture unit 8/8,
  `tsc` clean. Not run: Python lint/type check (none configured), evals (no LLM field).

### T-006 · LLM client wrapper (`structured()`), OpenAI adapter, pricing, call log
**Milestone:** M0 · **Size:** M · **Owner:** build
**Traces to:** architecture §6.1, §6.4, §6.5; rule 5; D-008 as amended by D-018.
**Done when:**
1. `LLMClient.structured()` works per §6.1, always validating the output with pydantic.
   The model comes from config, and a `model=` argument overrides it (`model=` >
   `llm.fields.<field>` > `llm.default`). The `--model` CLI flag moved to T-007 (D-027).
2. `adapters/openai.py` uses OpenAI's native structured output. Nothing outside
   `tutor/llm/` imports a provider SDK (SDK fence, §4.3 #2).
3. The retry and error table in §6.4 is implemented and unit-tested with `FakeAdapter`.
   A missing key, unknown model or missing price raises `LLMConfigError` before any call.
4. Every attempt writes one `logs/llm_calls.jsonl` line with all §6.5 fields. Bodies go to
   `logs/llm_bodies/<call_id>.json`, and cost comes from `config/pricing.toml`.
**Not included:** `chat()` and tool calls (M5); Anthropic adapter (M2); Gemini adapter (M7).
**Blocked on the human (resolved 2026-11-03, see log):** (a) confirm the OpenAI model id (`gpt-5.5` was taken from the old
repo); (b) enter its prices and `as_of` date in `config/pricing.toml`.
**Test assets:** required. `/test write T-006` covers the SDK-fence contract test, the
log-line schema, the retry table, and config errors.
**Log**
- 2026-11-03 Unblocked by the human: `gpt-5.5` confirmed as a listed OpenAI model id (pricing
  page screenshot), prices entered in `config/pricing.toml` — input $5.00 / 1M, output
  $30.00 / 1M, `as_of = 2026-11-03` (cached input $0.50 / 1M noted, not used). Ready for
  `/test write T-006`.
- 2026-11-03 `/test write T-006`. Interfaces agreed with the human (D-027): `model=` arg >
  `llm.fields` > `llm.default` (the `--model` flag moves to T-007); tester-owned FakeAdapter plus a
  fake OpenAI server on loopback; usage sums all attempts. Written: `tests/_llm_fake.py`;
  `tests/contract/test_llm_sdk_fence.py` (2: the fence, and grading the fence);
  `tests/contract/test_openai_adapter.py` (10: native JSON-schema output, tokens/cost, client-only
  retries on 5xx/429/timeout, no retry on 400/401, key from env and never logged, missing key and
  no-adapter provider fail before any request); `tests/acceptance/test_t006_llm_client.py` (35:
  Done-when 1, 3, 4). Result: 45 fail, all `ModuleNotFoundError: tutor.llm` (right reason); the
  2 fence tests pass. Rest of the suite unchanged (144 passed, 6 skipped). The builder adds the
  `openai` dependency.
- 2026-11-03 `/test write T-006` (fix). `test_openai_adapter.py`: the fake server now stores
  header names lower-cased, and the key check reads `authorization`. Reason: HTTP header names
  are case-insensitive (RFC 9110). The SDK sends `authorization`, and the test wrongly assumed
  `Authorization`. The request did carry the right key; nothing the test checks was loosened.
- 2026-11-03 `/build T-006`. Built `src/tutor/llm/`: `errors.py`, `messages.py` (§6.2),
  `pricing.py`, `client.py` (`ModelRef`, `Usage`, `LLMResult`, `LLMClient.structured()` with the
  §6.4 retry loop and §6.5 logging), `adapters/__init__.py` (`AdapterResponse`, `Adapter`),
  `adapters/openai.py` (Responses API, strict `json_schema`, SDK retries off, `store=False`).
  Added dependency `openai` 3.44.0 (on `httpx2`). Unit tests: `tests/unit/test_llm_internals.py`
  (18). Suite: 205 passed, 6 skipped (`live_capture`) — T-006 contract 12/12, acceptance 35/35.
  Decisions: D-028. Eval: n/a (no field uses the client yet). Cost: $0.
- 2026-11-03 `/test run` → ✅. The builder's diff (`5a0ba0f`) touches no judging files.
  Python: contract 38, acceptance 115 (+6 `live_capture` skipped; run with `-m live_capture`:
  6/6), unit 52; total 205 passed. Capture: unit 8/8, contract 20/20, `tsc` clean.
  `tutor prompts check` ok. Done-when 1–4 met (model choice, pydantic validation, SDK fence,
  §6.4 retry table, config errors before any call, §6.5 log lines, bodies, cost from
  `pricing.toml`). Skipped gate: Python lint/types, not set up yet (open `/pm` follow-up).
  Evals: none apply. Cost: $0.

### T-007 · M0 checkpoint: load one session, make one logged call
**Milestone:** M0 · **Size:** S · **Owner:** build
**Traces to:** M0 checkpoint.
**Done when:**
1. `tutor smoke --session <id>` loads one real session from the frozen copy,
validates it, and makes one `structured()` call through the wrapper with a throwaway
prompt `prompts/smoke/v1.md` (returning `{problem_slug}` from the problem title). One
complete line appears in `llm_calls.jsonl` with a non-zero `cost_usd`.
2. `tutor smoke --model provider:model` overrides the configured model for that run: the
   call and its log line use the given model. A malformed value, or a provider with no
   adapter, exits non-zero with the `LLMConfigError` message before any call. (Moved from
   T-006 Done-when 1, D-027.)
**Not included:** any real field; the smoke prompt is never used by a field; `--model` on
other commands (each adds it when it is built, e.g. the eval runner for M7).
**Test assets:** required. `/test write T-007` writes an acceptance test marked `llm` that
checks the log line and the validated output, and non-`llm` tests for `--model` using the
fake OpenAI server from `tests/contract/test_openai_adapter.py`.
**Log**
- 2026-11-03 `/pm idea` — Done-when 2 added: the `--model` flag, moved from T-006 because no
  command called an LLM there (D-027). Not new scope: it was already in M0. Size stays S.
- 2026-11-03 `/test write T-007`. Interface pinned with the human (D-029). Written:
  `tests/acceptance/test_t007_smoke.py`: 9 default tests (Done-when 1: the load, the call, one
  complete log line with cost, the frozen copy read and unchanged, the smoke prompt in the
  manifest, an unknown or excluded session failing before any call; Done-when 2: `--model`
  overrides config, and a bad value fails before any call), plus 1 `llm` test, the real call
  (≈ $0.001, `uv run pytest -m llm tests/acceptance/test_t007_smoke.py`, for the human to run).
  The fake OpenAI server moved to the shared `tests/_fake_openai.py`; the T-006 contract test's
  checks are unchanged (10/10). Result: 9 fail for the right reason (`smoke` isn't a command
  yet, and there's no `prompts/smoke/v1.md`). Rest of the suite unchanged (205 passed).
- 2026-11-03 `/build T-007` → 🔄. `src/tutor/smoke.py` (`SmokeOutput`, `run_smoke`), `tutor smoke`
  in `cli.py`, `prompts/smoke/v1.md` + its manifest entry (by hand), and `LLMClient.model_for()`
  made public so smoke reports the model without repeating the lookup order. Unit tests:
  `tests/unit/test_smoke_internals.py` (3). Suite: 217 passed, 6 skipped, 1 deselected. **Real
  call, run with the human's OK:** the `llm` test passed; `tutor smoke --session ebd80323…` →
  `{"problem_slug": "two-sum"}`, call `a78fa7f3e49a78b2`, 88 in / 37 out tokens, $0.00155,
  1.7 s, one complete `llm_calls.jsonl` line. Cost this session: ≈ $0.003 (2 calls). D-030.
- 2026-11-03 `/test run` → ✅. The builder's diff (`fd193a4`) touches no judging files. Python:
  contract 38, acceptance 124 (+6 `live_capture` skipped; run with `-m live_capture`: 6/6), unit
  55. The `llm` real-call test, rerun by the tester: 1/1 (≈ $0.0015). Capture: unit 8/8,
  contract 20/20, `tsc` clean. `tutor prompts check` ok. Done-when 1 and 2 met. Scope: the
  change making `LLMClient.model_for()` public is small and serves Done-when 2 (D-030); not
  scope creep. Skipped gate: Python lint/types, not set up (open `/pm` follow-up). **M0
  checkpoint met:** one captured session loads and validates, and one logged LLM call runs.

## Tasks — M1 (✅ done 2026-11-03)

M0 closed 2026-11-03. Planned in detail 2026-11-03 (`/pm plan`). Order:
**T-013 → T-008 → T-009 → T-010 → T-011 → T-012**. T-010 reuses T-009's time helper (§5.1),
and T-011 needs T-008, T-009 and T-010. Each `required` task goes `/test write` → `/build` →
`/test run`.

| ID | Task | Owner | Size | Test assets | Status | Traces to |
|---|---|---|---|---|---|---|
| T-013 | Python lint + type gate: choose the tools with the human, configure them, make the current code pass, and give `/test run` the command | build | S | none | ✅ 2026-11-03 `/test run` | `/test run` gate table ("Lint + types", blocking); skipped in every verdict T-003 – T-007 |
| T-008 | `analysis.db` migrations: `0001_init.sql` + `migrate.py` (refuses the capture path) | build | M | required | ✅ 2026-11-03 `/test run` | arch §3.2–3.3 |
| T-009 | Condenser `c1`: `condense` / `render` / `change_summary`, `CondensedSession`, `Moment`, budget truncation | build | M | required | ✅ 2026-11-03 `/test run` | arch §5; eval-plan condensing tests; D-006, D-013 |
| T-010 | Deterministic fields: problem, time to finish, attempted at (UTC + local date), status table + `status_source`; set `capture.submits_reliable_since = 2026-11-04` in `tutor.toml` (D-024), whose T-003 test `/test write T-010` updates | build | M | required | ✅ 2026-11-03 `/test run` | arch §4.3, §5.1; D-014, D-019, D-020 |
| T-011 | Deterministic pipeline: `tutor analyze` writes `sessions` + `condensed_timelines`; `tutor rebuild-timelines`; `tutor check` | build | M | required | ✅ 2026-11-03 `/test run` | arch §5.6, §13; D-012 |
| T-012 | M1 checkpoint: all unit/contract tests green on the 8 real + hand-built sessions; token budget measured (max / median est. tokens recorded here) | test | S | required | ✅ 2026-11-03 `/test run` | M1 checkpoint; eval-plan condensing tests |

### T-013 · Python lint + type gate
**Milestone:** M1 · **Size:** S · **Owner:** build
**Traces to:** the `/test run` gate table ("Lint + types", blocking). Skipped in every verdict
from T-003 to T-007 because nothing was configured.
**Done when:**
1. A linter and a type checker, chosen with the human at `/build` and recorded in
   `docs/decisions.md`, are dev dependencies configured in `pyproject.toml`.
2. One command runs both and exits 0 on the current code: lint over `src/` and `tests/`, types
   over `src/` only (narrowed by the human at `/build`, D-031). The command is written in this
   task's log, and `/test run` uses it from then on.
3. The suite still passes (217 + 6 `live_capture`).
**Not included:** TypeScript lint (the capture code already has `tsc`); pre-commit hooks;
CI; rewriting code beyond what the tools flag.
**Test assets:** none. The gate is the check.
**Log**
- 2026-11-03 `/build T-013` → 🔄. The human chose the lean gate with mypy (D-031). Dev deps:
  ruff 0.17.3, mypy 2.4.1. `pyproject.toml`: `[tool.ruff.lint] select = ["E4","E7","E9","F"]`
  (named explicitly: ruff 0.17's default set is wider and flagged 24), and `[tool.mypy]` on
  `src/` with the pydantic plugin. Fixed the 2 mypy findings in builder code: the OpenAI adapter
  now builds its request with the SDK's typed params (a `tool` message raises), and
  `LLMResult(...)` is no longer subscripted at runtime. **Gate command:**
  `uv run ruff check src tests && uv run mypy` → all checks passed; no issues in 16 files.
  Suite: 217 passed, 6 skipped, 1 deselected.
- 2026-11-03 `/test run` → ✅. The builder's diff (`5460917`) touches no judging files.
  **Lint + types (first time this gate ran):** `uv run ruff check src tests && uv run mypy`, all
  checks passed, no issues in 16 files. Python: contract 38, acceptance 124 (+6 `live_capture`:
  6/6), unit 55. The adapter's request code changed, so the `llm` real-call test was rerun: 1/1
  (≈ $0.0015). Capture: unit 8/8, contract 20/20, `tsc` clean. `tutor prompts check` ok. Done-when
  1–3 met, with Done-when 2 narrowed to types on `src/` by the human (D-031). Note, not
  blocking: the adapter's new "a `tool` message raises" guard has no unit test. No caller sends
  one before `chat()` (M5).

### T-008 · `analysis.db` migrations
**Milestone:** M1 · **Size:** M · **Owner:** build
**Traces to:** architecture §3.2, §3.3; §2 (`db/migrate.py`, `tutor migrate`).
**Done when:**
1. `src/tutor/db/migrations/0001_init.sql` holds the §3.2 DDL exactly, with a header comment
   saying what happens to existing rows (§3.3). No migration file contains `IF NOT EXISTS`.
2. `tutor migrate` on a missing file creates `paths.analysis_db` with every §3.2 table and
   index, and records version 1 in `schema_migrations`. Running it again applies nothing and
   changes nothing.
3. Each migration runs in one transaction. A migration that fails partway leaves the database
   at the previous version, with no partial tables.
4. `migrate` refuses a target that resolves to `paths.capture_db` or `paths.eval_capture_db`,
   and opens neither file.
5. `src/tutor/db/migrations/manifest.json` records each migration's sha256. A contract test
   fails when a file and its entry differ.
6. The CHECK constraints reject bad values: an unknown `status`, `status_source`,
   `failure_type` or algorithm label, and a `truncated` other than 0 or 1.
**Not included:** writing any rows (T-011); the read-only connection for the Progress Agent
(M5, Part 2); the fixture DB (M5).
**Test assets:** required. `/test write T-008` writes the migration-manifest contract test, the
capture-path refusal, and acceptance tests for Done-when 2, 3 and 6.
**Log**
- 2026-11-03 `/test write T-008`. Interfaces pinned with the human (D-032). Written:
  `tests/contract/test_migrations.py` (11 tests: at least one migration; hashes match
  `migrations/manifest.json`; numbering with no gaps; no `IF NOT EXISTS`; refusal of both
  capture DBs by plain path, `..` path and symlink, and of a capture DB that doesn't exist yet,
  without creating it); `tests/acceptance/test_t008_migrations.py` (17 tests: Done-when 1, the
  schema equals architecture §3.2's DDL, plus a header about rows; Done-when 2, creates every
  table and index, version 1 recorded, second run a no-op, CLI default and `--db`, refusal exit
  1; Done-when 3, a failing `0002` rolls back to version 1 with no partial table or rows, then
  applies once fixed; Done-when 6, valid rows accepted, and 8 bad values rejected). Checked the
  tests against the §3.2 DDL directly: they pass on it. Result: 26 fail for the right reason
  (no `tutor.db`, no `migrate` command, no `0001_init.sql`); 2 contract tests pass vacuously
  while there are no files, and the at-least-one test covers that. Rest of the suite unchanged.
- 2026-11-03 `/test write T-008` (fix). The two Done-when 3 tests' hand-built `0001` now creates
  `schema_migrations`. Reason: in §3.2, `0001` creates `schema_migrations` itself; the tests'
  fake migrations didn't, so `migrate` failed before reaching the broken `0002`. Nothing the
  tests check was loosened: rollback to version 1, no partial table, no leftover rows, and
  the fixed migration then applies.
- 2026-11-03 `/build T-008` → 🔄. `src/tutor/db/`: `migrations/0001_init.sql` (§3.2 DDL copied
  programmatically from the architecture, plus a header on existing rows and rebuild cost),
  `migrations/manifest.json`, `migrate.py` (`discover`, `current_version`, `migrate`,
  `MigrationError`). `tutor migrate [--db]` added to `cli.py`. Each file runs as `BEGIN;` + file
  via `executescript` on an autocommit connection, the version row is inserted with bound
  params, then `COMMIT`; any error → `ROLLBACK` + `MigrationError` naming the file. Unit tests:
  `tests/unit/test_migrate_internals.py` (12). Gate clean (ruff; mypy 18 files). Suite: 257
  passed, 6 skipped, 1 deselected — T-008 contract 11/11, acceptance 17/17. D-033.
- 2026-11-03 `/test run` → ✅. The builder's diff (`6f1a31b`) touches no judging files; the one
  test change (`2fff4df`) came through `/test write` with a written reason. Lint + types clean
  (ruff; mypy 18 files). Python: contract 49, acceptance 141 (+6 `live_capture`: 6/6), unit 67.
  Capture: unit 8/8, contract 20/20, `tsc` clean. `tutor prompts check` ok. Done-when 1–6 met;
  also checked that the body of `0001_init.sql` is byte-identical to the §3.2 SQL block. Cost: $0.

### T-009 · Condenser `c1`
**Milestone:** M1 · **Size:** M · **Owner:** build
**Traces to:** architecture §5.1–§5.5, §4.1 (`ChangeSummary`, `Moment`, `CondensedSession`);
eval-plan condensing step and its unit tests; D-006, D-013, D-026.
**Done when:** `condense`, `render` and `change_summary` in `src/tutor/condense.py` meet §5,
checked on hand-built sessions:
1. **Every run and submit is kept, with its result** (eval plan). A backfilled submit
   (`ts=None`) comes after `final` as "SUBMIT (time not captured)".
2. **A snapshot every 2 minutes while the code changes, plus one at each run and submit**
   (eval plan). A tick whose code equals the last kept code is skipped. A run or submit on
   unchanged code gets `code=None` with `code_ref`. `opened` and `final` are always present.
3. **Elapsed times match the raw timestamps** (eval plan): `t0`, `t_end` and `duration_min`
   follow §5.1, and ties order `timed < run < submit < final`.
4. `change_summary` follows §5.3. A rewrite (≥ 50% changed) sets `rewrite`.
5. `render` follows §5.5. `error_detail` is cut at `condenser.error_max_chars` with
   "… [truncated]".
6. **A hand-built 60-minute session fits 16,000 estimated tokens** (eval plan). An
   over-budget session drops `timed` code earliest first, keeps its change summary, and sets
   `truncated`. If it's still over, `CondenseBudgetError` is raised.
7. Pure: the same input gives byte-identical `render` output. No I/O, clock or randomness.
**Not included:** storing timelines (T-011); measuring real sessions (T-012); stuck periods
(deferred, D-026); any LLM field.
**Test assets:** required. `/test write T-009` writes hand-built sessions with known
timestamps. Each eval-plan condensing test is a named acceptance test.
**Log**
- 2026-11-03 `/test write T-009`. Three spec gaps settled by the human (D-034, architecture
  §4.1/§5.2/§5.5 updated): `Moment.submit`, FINAL always last, and ` · REWRITE` in the render.
  Written: `tests/acceptance/test_t009_condenser.py` (28 tests): two hand-worked sessions
  checked moment by moment (captured submit, backfilled submit); the 4 eval-plan condensing
  tests by name (every run and submit kept; a snapshot every 2 min while code changes, plus
  each run and submit; elapsed times match; a 60-min worst-rate session fits 16k untruncated);
  opened and final always present; snapshot lag; `code_ref` targets; t0 and t_end; tie order;
  `change_summary` on 5 hand-worked cases (checked against `difflib` directly); render
  header, moment lines, backfilled line, REWRITE, error truncation, `est_tokens`; budget
  truncation (earliest timed first) and `CondenseBudgetError`; determinism. Result: 28 fail
  for the right reason (`No module named 'tutor.condense'`). Rest of the suite unchanged
  (257 passed).
- 2026-11-03 `/build T-009` → 🔄. `src/tutor/condense.py`: `CONDENSER_VERSION = "c1"`,
  `CondenseBudgetError`, `session_times` (the §5.1 helper T-010 reuses), `change_summary`,
  `condense` (one sorted walk over opened / ticks / events / final candidates, then backfilled
  submits, then budget truncation), `render`. `models.py`: `ChangeSummary`, `Moment` (with
  `submit`), `CondensedSession` (plus `language`, D-035). Unit tests:
  `tests/unit/test_condense_internals.py` (6). Gate clean (mypy, 19 files). Suite: 291 passed,
  6 skipped, 1 deselected; T-009 acceptance 28/28. Builder smoke run on the 8 frozen sessions
  (read-only): every run and submit kept, none truncated, est. tokens max 5,956 / median
  2,256. T-012 records these officially. D-035.
- 2026-11-03 `/test run` → ✅. The builder's diff (`e6227da`) touches no judging files. Lint + types
  clean (mypy, 19 files). Python: contract 49, acceptance 169 (T-009 28/28; +6 `live_capture`:
  6/6), unit 73. Capture: unit 8/8, contract 20/20, `tsc` clean. `tutor prompts check` ok.
  Purity checked by reading the module: it imports only `bisect`, `difflib`, `datetime`,
  `typing` and `tutor.models`, with no I/O, clock or randomness. Done-when 1–7 met. Scope: the
  added `CondensedSession.language` field is needed for §5.5's code fences and is recorded as
  D-035. Not creep, but architecture §4.1 doesn't list it yet (for `/architect`). Cost: $0.

### T-010 · Deterministic fields: problem, time to finish, attempted at, status
**Milestone:** M1 · **Size:** M · **Owner:** build
**Traces to:** architecture §4.2, §4.3, §5.1; eval-plan field table; D-014, D-019, D-022, D-024.
**Done when:** `src/tutor/fields/deterministic.py`:
1. **Problem** returns the session's slug, title, difficulty and tags.
2. **Time to finish** uses the same §5.1 helper as the condenser, so it equals
   `duration_min`: first event to the last captured submit, else the last event. It is
   rounded to 1 decimal.
3. **Attempted at** gives the first event in UTC and the local date in `time.timezone`
   (America/New_York). A session after 8 pm New York time gets the earlier local date, and a
   session on 2026-11-01 (the DST change) gets the right date.
4. **Status** follows every row of the §4.3 table, including `failed_output_limit` (D-022),
   `not_submitted` versus `unknown` by `submit_capture_reliable`, and an unmapped verdict:
   `unknown`, logged as `unmapped_verdict` without raising. `leetcode_verdict`, the test counts
   and `status_source` come from the final submit.
5. `tutor.toml` sets `capture.submits_reliable_since = "2026-11-04"` (D-024, the human's T-001
   decision). `/test write T-010` updates the T-003 test that asserts it is unset, with a
   written reason.
6. Nothing in this module calls an LLM or imports `tutor.llm`.
**Not included:** failure type or any LLM field (M3); writing rows (T-011).
**Test assets:** required. `/test write T-010` writes one acceptance test per status-table row
and the time zone and DST date cases.
**Log**
- 2026-11-03 `/test write T-010`. Interfaces pinned with the human (D-036). Written:
  `tests/acceptance/test_t010_deterministic.py` (31 tests):
  - Done-when 1: problem.
  - Done-when 2: time to finish ends at the last captured submit, or the last event; equals
    `condense().duration_min` on 4 sessions.
  - Done-when 3: 5 New York date cases checked against the IANA tz database (the day before in
    New York; 01:30 EDT and 01:30 EST across the DST change; 22:30 EST; after 8 pm), plus
    first event before the first snapshot, and the timezone read from settings.
  - Done-when 4: all 7 table rows, an unmapped verdict logged, `not_submitted` vs `unknown` by
    reliability, the final submit decides, runs aren't submits, backfill is `human_resubmit`,
    and the enum values.
  - Done-when 5: `submits_reliable_since` loads as 2026-11-04.
  - Done-when 6: no `tutor.llm` import.
  Also updated two asserts in `test_t003_skeleton.py` that required the cutoff to be unset.
  Reason: the human set 2026-11-04 in T-001 and T-010 writes it (Done-when 5); the T-003
  checks were written before that decision. Result: 33 fail for the right reason (no
  `tutor.fields`, no enums, cutoff not yet in `tutor.toml`). Rest of the suite unchanged.
- 2026-11-03 `/test write T-010` (fix). `test_t004_loader.py`'s `settings_for(since=None)` now
  loads a copy of `tutor.toml` without `submits_reliable_since`. Reason: its "unset → never
  reliable" case relied on the real file having no cutoff, which T-010 changes (Done-when 5).
  An env var can't unset a key, so the copy is the only true "unset". A miss in this task's
  first `/test write`, which updated the two T-003 checks but not this one. Nothing the test
  checks was loosened.
- 2026-11-03 `/build T-010` → 🔄. `models.py`: `Status`, `StatusSource`. New
  `src/tutor/fields/deterministic.py`: `problem`, `time_to_finish` (through `session_times`),
  `attempted_at` (`zoneinfo`), `status` (a `STATUS_BY_VERDICT` dict that reads row for row like
  §4.3, keyed by `Verdict`, plus the no-submit rules; unmapped verdicts logged), and
  `StatusResult`, kept in the field module because nothing else needs it before T-011.
  `tutor.toml`: `submits_reliable_since = "2026-11-04"`. Unit tests:
  `tests/unit/test_deterministic_internals.py` (3). Gate clean (mypy, 21 files). Suite: 325
  passed, 6 skipped, 1 deselected; `live_capture` 6/6, so the frozen sessions are still "not
  reliable". T-010 acceptance 31/31.
- 2026-11-03 `/test run` → ✅. The builder's diff (`34a4ed7`) touches no judging files; the one
  test change (`57b3c82`) came through `/test write` with a written reason. Lint + types clean
  (mypy, 21 files). Python: contract 49, acceptance 200 (T-010 31/31; +6 `live_capture`: 6/6),
  unit 76. Capture: unit 8/8, contract 20/20, `tsc` clean. `tutor prompts check` ok. Done-when
  1–6 met. Extra check on real data (read-only, frozen copy): status gives 7 `passed` + 1
  `failed_wrong_answer`, all `human_resubmit`, which matches the human's `verdicts.csv` for the
  8 sessions. Cost: $0.

### T-011 · Deterministic pipeline: `tutor analyze`, `rebuild-timelines`, `check`
**Milestone:** M1 · **Size:** M · **Owner:** build
**Traces to:** architecture §5.6, §13, §2 (`analyzer/pipeline.py`, `cli.py`); D-012.
**Done when:**
1. `tutor analyze [--since DATE]` loads sessions from `paths.capture_db` (`mode=ro`). In one
   transaction it upserts `problems`, `sessions` (T-010's facts, plus run and submit counts)
   and `condensed_timelines` (T-009 output, `est_tokens`, `truncated`) into a migrated
   `paths.analysis_db`. It refuses to run on an unmigrated DB.
2. Running it twice on the same capture leaves identical rows, except `loaded_at` and
   `built_at`.
3. `pipeline.jsonl` gets one line per session: `loaded`, `excluded` with its reason, or
   `condensed`.
4. `tutor rebuild-timelines` re-condenses every loadable session in one transaction. A stored
   timeline whose session no longer loads is kept and logged as `orphaned`.
5. `tutor check` lists `session_analysis` rows whose `condenser_version` differs from their
   timeline's, and exits non-zero when any exist.
6. The capture DB file is byte-identical after any of these commands. No `session_analysis`
   column is written.
**Not included:** LLM fields (M3–M4); the eval runner (M2); `--since` beyond a start-date
filter.
**Test assets:** required. `/test write T-011` writes acceptance tests on a tiny capture DB
for each Done-when.
**Log**
- 2026-11-03 `/test write T-011`. Interfaces pinned with the human (D-037). Written:
  `tests/acceptance/test_t011_pipeline.py` (18 tests, run in-process on a 4-session capture DB:
  passed, runs-only before the cutoff, excluded, and a later session for `--since`):
  - Done-when 1: hand-worked `sessions`, `problems` and `condensed_timelines` rows; the stored
    JSON re-renders to the stored text; refuses a missing or unmigrated DB without creating it;
    one transaction, with a config budget that fails on the 3rd session and leaves nothing
    written.
  - Done-when 2: a second run gives identical rows; a new submit updates in place.
  - Done-when 3: one log outcome per session, one run id.
  - Done-when 4: rebuild rewrites every timeline; orphan kept and logged; a failed rebuild
    changes nothing.
  - Done-when 5: `check` passes, passes when versions match, fails and names a stale session.
  - Done-when 6: capture DB byte-identical; no analysis rows written.
  - `--since` local date.
  Checked the expected values against the already-verified loader, condenser and fields
  first: all 3 sessions match, and the 600-token budget fails only on the 3rd. Result: 18 fail
  for the right reason (`analyze` is not a command yet). Rest of the suite unchanged.
- 2026-11-03 `/build T-011` → 🔄. `src/tutor/analyzer/pipeline.py`: `open_analysis_db` (`mode=rw`,
  so it never creates the file; refuses capture paths and old migrations), `analyze`,
  `rebuild_timelines`, `check`, `PipelineError`. Each command loads and condenses in memory,
  then writes everything in one `BEGIN … COMMIT` of upserts. CLI: `analyze [--since]`,
  `rebuild-timelines`, `check`. `migrate.refuse_capture` made public for reuse. Unit tests:
  `tests/unit/test_pipeline_internals.py` (7). Gate clean (mypy, 23 files). Suite: 350 passed,
  6 skipped, 1 deselected; T-011 acceptance 18/18. **Run on the live capture DB, read-only,
  into a scratch analysis.db:** 24 sessions stored and rebuilt, `check` ok, capture hash
  unchanged. Statuses: 11 `passed`, 2 `failed_too_slow`, 2 `failed_wrong_answer`, 9 `unknown`
  (`not_captured`: before the cutoff, no captured submit). Max 5,956 est. tokens, none
  truncated. D-038.
- 2026-11-03 `/test run` → ✅. The builder's diff (`c702044`) touches no judging files. Lint + types
  clean (mypy, 23 files). Python: contract 49, acceptance 218 (T-011 18/18; +6 `live_capture`:
  6/6), unit 83. Capture: unit 8/8, contract 20/20, `tsc` clean. `tutor prompts check` ok.
  Done-when 1–6 met. Read the code: the capture DB is only reached through `CaptureLoader(...,
  mode="ro")`; the one `mode=rw` connection is `analysis.db`. The small change in `migrate.py`
  (`refuse_capture` made public) is reuse, not creep. Cost: $0.

### T-012 · M1 checkpoint: real sessions condensed, token budget measured
**Milestone:** M1 · **Size:** S · **Owner:** test
**Traces to:** M1 checkpoint; eval-plan condensing tests and token budget.
**Done when:**
1. Every test is green: contract, acceptance, unit, `live_capture`, and lint/types (T-013).
2. All 8 frozen sessions condense with every run and submit kept and within budget. Max and
   median `est_tokens` are recorded in this task's log, against the ≈ 2,400 average in
   `session-format.md`.
3. The human reads the rendered timeline of 2 real sessions and confirms in this log that it
   matches what happened. This is a tester-owned task, so it can't close without that.
**Not included:** live-DB sessions beyond the frozen 8; any LLM call.
**Test assets:** required. A `live_capture` acceptance test over the frozen copy.
**Log**
- 2026-11-03 `/test write T-012`. Written: `tests/acceptance/test_t012_m1_checkpoint.py`
  (4 tests, `live_capture`, frozen copy opened immutable): all 8 condense; every run and submit
  is in its timeline; each fits the budget untruncated; the stored JSON re-renders identically.
  These check code that already exists, so they pass now: 4/4.
  **Token budget measured (Done-when 2), c1, default settings:** est. tokens per session
  484 / 773 / 1,209 / 1,352 / 3,160 / 3,419 / 4,952 / 5,956. **Max 5,956, median 2,256**,
  vs the ≈ 2,400 average in `session-format.md` and the 16,000 budget; none truncated.
  Two rendered timelines written locally (scratchpad, not committed: they hold the human's
  code) for the human's Done-when 3 review: `sort-colors` 81224169 (the Wrong Answer
  59/90 session, 24.3 min, 5 runs, 18 moments) and `coin-change` be762faa (6 runs, the most).
  Note: architecture §5.5's example of this sort-colors session says 24.4 min; the real
  duration is 24 min 20 s = 24.3, so the example was approximate. **Waiting on the human's
  confirmation.**
- 2026-11-03 **Human confirmation (Done-when 3):** the human read both rendered timelines
  (`sort-colors` 81224169, `coin-change` be762faa) and confirmed: "these timelines look
  correct". Ready for `/test run`.
- 2026-11-03 `/test run` → ✅. Since T-011's ✅, only tester commits (`1ed2b66`, `bf29755`).
  Done-when 1, every gate green: lint + types clean (ruff; mypy 23 files); contract 49;
  acceptance 218 (+10 `live_capture`: 10/10, including T-012's 4); unit 83; capture unit 8/8,
  contract 20/20, `tsc` clean; `tutor prompts check` ok. Done-when 2: measured and recorded
  above (c1: max 5,956, median 2,256 est. tokens, none truncated). Done-when 3: the human's
  confirmation is in this log. **M1 checkpoint met.** Cost: $0.

**Stuck periods → course correction (2026-11-03, D-026).** Measured on 26 real sessions
(`scripts/discovery/18_stuck_periods.py`), the "no edits for 6+ min" rule never fired, so stuck
periods are deferred. The timeline summary instead says whether the first approach was on the
right track and whether / when the user course-corrected. No condenser change (rewrite flags,
D-013, already show new approaches); M2 labels gain `course_correction`; M4's checklist checks it.

## Tasks — active milestone: M2

Planned 2026-11-07. Already done ahead of the plan (in the session log): the `synthetic-spec`
skill, the spec checker, and 20 human-approved specs, each with LeetCode-checked final code
(D-039 – D-045). Order: **T-014 → T-015 → T-016 → T-017 → T-018 → T-019 → T-021 → T-022 → T-023**.
T-020 (labelling the real sessions) is human work and can happen any time before T-021.

| ID | Task | Owner | Size | Test assets | Status | Traces to |
|---|---|---|---|---|---|---|
| T-014 | Migration `0002_add_prefix_sum.sql`: recreate `session_algorithms` with `prefix_sum` in the label CHECK, keeping rows; `AlgorithmLabel` gets the value | build | S | required | ⬜ | D-044; arch §3.3 |
| T-015 | Anthropic adapter (`adapters/anthropic.py`), the same contract as OpenAI's | build | M | required | ⏸ human: confirm the generator model id + enter its price | arch §6; D-008, D-018 |
| T-016 | Eval cases + split guard (`tutor/evals/cases.py`) | build | M | required | ⬜ | arch §8.1, §8.2, §4.3 #1 |
| T-017 | Session checks (`evals/generate/checks.py`) | test | M | required | ⬜ | arch §8.5; D-043 |
| T-018 | Session generator + prompt `generators/session/v1` | test | M | required | ⬜ | arch §8.5; D-017, D-043 |
| T-019 | Generate the 20 sessions; human reviews each | test | M | required | ⬜ | arch §8.5; D-017 |
| T-020 | Label the 8 real sessions | test | M | required | ⬜ | eval plan "Dataset"; D-026, D-039 |
| T-021 | Assemble `dev-v1` + test split, `cases.jsonl` per suite | test | S | required | ⬜ | arch §8.1; eval plan "Dataset" |
| T-022 | Eval runner, result record, `estimate`; overlap grader + keyword baseline | build | M | required | ⬜ | arch §8.2 – §8.4; eval plan algorithm metric |
| T-023 | M2 checkpoint: keyword baseline on `algorithm` dev-v1 → versioned record + baseline row | test | S | required | ⬜ | M2 checkpoint |

### T-014 · Migration 0002: `prefix_sum` label
**Milestone:** M2 · **Size:** S · **Owner:** build · **Traces to:** D-044; arch §3.3.
**Done when:**
1. `0002_add_prefix_sum.sql` recreates `session_algorithms` with `'prefix_sum'` added to the
   CHECK, in one transaction, copying existing rows. Its header says what happens to them.
2. The manifest gets 0002's hash. `tutor migrate` takes a version-1 DB to 2, and a fresh DB to 2.
3. Rows present before 0002 are still present after it. `prefix_sum` is accepted, an off-list
   label is still rejected, and `AlgorithmLabel` includes `prefix_sum`.
**Not included:** any other schema change.
**Test assets:** required (upgrade-with-rows and CHECK tests).
**Log**

### T-015 · Anthropic adapter
**Milestone:** M2 · **Size:** M · **Owner:** build · **Traces to:** arch §6.1, §6.4, §6.5; D-008, D-018.
**Done when:**
1. `adapters/anthropic.py` implements the D-027 adapter interface with native structured output
   (JSON schema). The SDK's own retries are off, the key is read from `ANTHROPIC_API_KEY`, and a
   missing key is `LLMConfigError`.
2. The same contract tests as OpenAI pass against a loopback fake Anthropic server: the
   schema is sent, 429, 5xx and timeouts are retried by the client only, 4xx is not retried, and
   the key is never logged.
3. `config/pricing.toml` has the generator model's price, entered by the human. One `llm`-marked
   real call succeeds and is logged with its cost.
**Not included:** `chat()` / tool use (M5); using Claude for any Part 1 field.
**Blocked on the human:** confirm `llm.generator` (`anthropic:claude-opus-5-5`) and its prices.
**Test assets:** required.
**Log**

### T-016 · Eval cases + split guard
**Milestone:** M2 · **Size:** M · **Owner:** build · **Traces to:** arch §8.1, §8.2 (split guard), §4.3 #1 (label fence).
**Done when:**
1. `tutor/evals/cases.py` loads `evals/data/<suite>/<split>/cases.jsonl` into a `Case` model.
   Real cases load their `Session` from the frozen copy, opened immutable. Synthetic cases load
   theirs from `synthetic_path`, and are refused unless `<id>.meta.json` says
   `"verdict": "accepted"`.
2. **Split guard:** reading `test` is refused unless `--split test --milestone <id>` is given and
   `<id>` is listed in `evals/test_approvals.json`. Paths are checked after resolving.
3. **Label fence (contract):** no module under `src/tutor/` outside `tutor/evals/` reads
   `evals/data/`, and the runner hands field functions a `Session`, never a `Case` or `expected`.
**Not included:** running fields or grading (T-022); writing cases (T-021).
**Test assets:** required (split-lock and label-fence contract tests).
**Log**

### T-017 · Session checks
**Milestone:** M2 · **Size:** M · **Owner:** test · **Traces to:** arch §8.5 checks; D-043.
**Done when:** `evals/generate/checks.py` rejects a generated session, with a logged reason, if:
1. it doesn't validate as `Session`, offsets don't increase, snapshots are under 5 s apart, or two
   snapshots in a row are identical;
2. its duration or run count is more than ±20% off the spec;
3. its final snapshot differs from `final_code/<id>.py`, or its submit verdict and counts differ
   from the spec;
4. **leak check:** a comment or any run output names a label (failure type, an algorithm label or
   its display name) or quotes a key fact. Code identifiers like `stack` or `heapq` are allowed,
   because real code has them;
5. it doesn't condense within the token budget.

Each rule is graded on hand-made passing and failing sessions.
**Not included:** generation (T-018).
**Test assets:** required (the check's own tests). Closes with the human's confirmation in the log.
**Log**

### T-018 · Session generator
**Milestone:** M2 · **Size:** M · **Owner:** test · **Traces to:** arch §8.5; D-017, D-043.
**Done when:**
1. `uv run python -m evals.generate.sessions --spec <id> | --all [--estimate]` calls
   `llm.generator` through `LLMClient.structured` with `prompts/generators/session/v1.md`. It
   refuses to run when the generator and `llm.default` share a provider.
2. The model writes only the lead-up snapshots (offsets plus code) and each Run's status and
   output. Code assembles the `Session`: a fixed base time, problem metadata, the human's final
   code as the last snapshot, and the submit copied from the spec.
3. Each session passes T-017's checks, or is rejected and logged. `<id>.json` and an unreviewed
   `<id>.meta.json` are written with their provenance. `--estimate` prints the cost and makes
   no calls.
4. One spec is generated end to end, with a real call (`llm` marker), and its cost recorded.
**Not included:** reviewing (T-019); a `tutor-eval` subcommand (the entry point is the tester's
module; D-046 amends §8.5).
**Test assets:** required (a fake-adapter run, the provider refusal, the estimate). Closes with
the human's confirmation.
**Log**

### T-019 · Generate and review the 20 sessions
**Milestone:** M2 · **Size:** M · **Owner:** test · **Traces to:** arch §8.5 human review; D-017.
**Done when:**
1. `--estimate` is shown to the human and approved before the `--all` run. The actual cost is
   recorded here.
2. All 20 sessions pass the checks. The human reads each rendered timeline, and `meta.json`
   records `accepted` or `rejected`. A rejected session is regenerated after a *general*
   prompt fix (rule 9), and the prompt version is bumped.
3. 20 are accepted, with the human's confirmation in this log.
**Not included:** splitting (T-021).
**Test assets:** required (the reviewed sessions are the asset). Closes with the human's
confirmation.
**Log**

### T-020 · Label the 8 real sessions
**Milestone:** M2 · **Size:** M · **Owner:** test · **Traces to:** eval plan "Dataset" (the human
labels algorithm, failure type, course correction, key facts); D-026, D-039.
**Done when:** for each frozen session the tester proposes `failure_type`, `algorithms`,
`course_correction`, `on_track_algorithms` and 2–4 key facts, each with a one-line reason read off
the rendered timeline. The human confirms or corrects every one, and they are stored as label
records for T-021. `check_specs.py --with-real` then counts their failure types and algorithms in
the balance.
**Not included:** new real sessions (a frozen-copy refresh is a later dataset version).
**Test assets:** required (the labels are the asset). Closes with the human's confirmation.
**Log**

### T-021 · Assemble dev-v1 and the test split
**Milestone:** M2 · **Size:** S · **Owner:** test · **Traces to:** arch §8.1; eval plan "Dataset".
**Done when:**
1. The 28 cases split **19 dev / 9 test** (D-045 re-proportions 20/10), balanced by status and
   by real vs synthetic. The human approves the split.
2. `evals/data/{failure,algorithm,timeline}/{dev,test}/cases.jsonl` are written in the §8.1
   format, with provenance and `dataset_version: dev-v1`, and their hashes are committed.
3. Test cases are reported by count only, anywhere a builder reads.
**Not included:** the `agent` suite (Part 2).
**Test assets:** required. Closes with the human's confirmation.
**Log**

### T-022 · Eval runner, result record, estimate
**Milestone:** M2 · **Size:** M · **Owner:** build · **Traces to:** arch §8.2 – §8.4; eval plan
algorithm metric ("any overlap counts", keyword baseline).
**Done when:**
1. `tutor-eval estimate` and `tutor-eval run --suite <s> --split dev [--model] [--repeats]` call
   the same field functions as the pipeline. They write `evals/results/<suite>/<run_id>.json`
   plus an `index.jsonl` line in the §8.3 format: every version, per-case outputs, cost, and
   aggregates overall / real / synthetic.
2. Every printed number carries its versions.
3. Tester-owned: `evals/graders/` with the §8.4 `Grader` interface, an algorithm overlap grader,
   and the keyword-matching baseline, each graded on hand-made outputs.
**Not included:** LLM fields (M3); judges (M4).
**Test assets:** required (grader tests, the result-record schema, the split lock through the runner).
**Log**

### T-023 · M2 checkpoint
**Milestone:** M2 · **Size:** S · **Owner:** test · **Traces to:** M2 checkpoint.
**Done when:** `tutor-eval run --suite algorithm --split dev` with the keyword baseline as the
"model" writes a versioned result record ($0). The number goes in the Baselines table as
`algorithm — keyword baseline @ dataset dev-v1`, with its real-only and synthetic-only values.
**Test assets:** required.
**Log**

**Later milestones (one line each until M1 closes):** M2: specs + Claude generator
+ review loop, Anthropic adapter, dataset split, runner and result record with real/synthetic
breakdown. M3: algorithm and failure-reason fields with dev baselines. M4: timeline +
judge calibration. M5–M6 (Part 2) deferred until Part 1 is done (human, 2026-11-03).
M7: Gemini adapter, Part 1 model comparison, first test-split run.

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
| Part 2: Progress Agent, `run_sql`, fixture DB, Part 2 evals (M5, M6, Part 2 half of M7) | Human, 2026-11-03: Part 1 first | Part 1's M7 model comparison ✅ |
| `tutor prompts lock` (write manifest entries by command) | Two prompts so far, one hash entered by hand (D-030); the contract test catches any mismatch | M3 adds the field prompts, or a hand-entered hash causes a wrong commit |
| Rule-based stuck periods in the condenser (eval plan 2026-11-03) | Rule B never fired on 26 real sessions; rule A only with a loose "same status" match (D-026) | Real sessions show long no-edit stretches, or the timeline eval misses struggles the summary can't see |

## Dropped

| Idea | Why | Date |
|---|---|---|
| Reword T-003 Done-when 1 | T-003 is ✅; rewording a closed task changes nothing | 2026-11-03 |

---

## Session log

| Date | Completed | Started | Added | Notes |
|---|---|---|---|---|
| 2026-11-02 | — | — | T-001, T-002 | `/pm idea`: submit capture fix added to M0 (eval-plan build order 1). T-001 finding written (`/v2/check/` regex miss). T-002 added (D-015, capture moves here; capture only). `/pm plan` not yet run. |
| 2026-11-02 | — | — | T-003 – T-007 (M0); T-008 – T-012 reserved (M1) | `/pm plan` (first plan). M0 = 7 tasks, 2 of them capture. Baselines table: status rows removed (D-014). |
| 2026-11-03 | T-001, T-004, T-005, T-006, T-007; **M0 ✅** | — | T-013 | `/pm review`, the first. Repo matches the tracker: every M0 task has `/test write` → `/build` → `/test run` with commits, and nothing is 🔄 or 👀. Unplanned work: one item, the human's extension rename (`c39c1c8`, 1 line in `manifest.json`), already noted in T-002's log; not a creep signal. Added since the plan: 1 (T-013). Deferred: 7 (+3 today: Part 2, stuck periods, `prompts lock`). Dropped: 1. Real LLM spend: ≈ $0.0045 (3 smoke calls); no eval runs yet. 10 commits on `m0-architecture-and-tests` not pushed. For `/architect`: §12 says "no test reads `data/`" but the `live_capture` tests and T-007's `llm` test do; §12 names no lint/type tools (T-013 decides them). |
| 2026-11-03 | — | — | — | `/pm plan` for M1: Done-when / Not included / test assets written for T-008 – T-013. No new tasks. Order T-013 → T-008 → T-009 → T-010 → T-011 → T-012. Branch `m1-deterministic` off `main`. |
| 2026-11-03 | T-013, T-008, T-009, T-010, T-011, T-012; **M1 ✅** | — | — | `/pm review`, M1 close. Repo matches the tracker: 21 commits since the last review, every one belonging to a task, nothing 🔄 or 👀, no unplanned work. Each task went `/test write` → `/build` → `/test run`; T-012 (tester-owned) has the human's confirmation. Added since the last review: 0. Completed: 6. Deferred: 7. **Quality signal:** two `/test write` fixes this milestone (T-008: fake migrations missing `schema_migrations`; T-010: a T-004 test that depended on `tutor.toml` having no cutoff). Both were caught by the builder before any ✅ and fixed with a written reason, but the tester should run the whole suite against a change's side effects before committing test assets. Real LLM spend: ≈ $0.0015 (1 smoke rerun); no eval runs. 21 commits on `m1-deterministic` not pushed. For `/architect`: §4.1 doesn't list `CondensedSession.language` (D-035); §5.5's example says 24.4 min where the real session is 24.3; plus the open §12 notes from the M0 review. Before M2's generator runs: an Anthropic price in `config/pricing.toml`. |
| 2026-11-07 | — | M2 dataset groundwork, ahead of `/pm plan` | — | Done on the human's direct request, before M2's tasks are written; `/pm plan` M2 will absorb it into the spec task. The `synthetic-spec` skill (`.claude/skills/synthetic-spec/`: workflow, label rules, a read-only problem-metadata lookup) and `evals/generate/check_specs.py` (tester-owned spec validator plus coverage table; graded on planted mistakes, all caught). D-039: specs carry `on_track_algorithms` (labels only). **3 specs approved by the human** ("this looks good"): syn-001 to syn-003 in `evals/data/sessions/synthetic/specs.jsonl`, split unassigned. Coverage gaps: too slow, runtime error, compile error, output limit, never-submitted, `implementation_bug`, `did_not_finish`, a corrected session. Open for M2's plan: refresh the frozen copy for more real sessions (unanswered), and an Anthropic price before generation. |
| 2026-11-07 | — | — | — | Dataset variety rule (D-040, the human's request). `check_specs.py` reports balance over real + synthetic (`--with-real`) and prints skew lines; the skill drafts batches against them. Today, with 8 real + 3 synthetic: 73% Accepted (max 35%), no Hard, 73% in 10–25 min, nothing over 25 min. The next specs should be mostly failing, include Hard problems, and run 25–60 min. Branch `m2-dataset` off `main`. |
| 2026-11-07 | — | — | — | D-041 (the human): difficulty is reported, not balanced; time spent is mostly 10–30 min, with at least one session under 10 and one over 30. Current skew: 73% Accepted (max 35%), and no session over 30 min. |
| 2026-11-07 | — | — | — | Spec batch 2: **15 specs approved by the human** (syn-004 – syn-007, syn-009 – syn-014, syn-016 – syn-020). syn-008 and syn-015 were dropped by the human and their ids retired. syn-019 and syn-020 (Memory Limit Exceeded) were added by the human, and syn-019's verdict was seen on LeetCode. syn-012 was relabelled `edge_case_missed`, 1/35, to match the human's code (crashes only on an empty tree). Python only (D-042). The human wrote the final code for 14 specs: in `synthetic/final_code/`, giveaway comments removed (D-043). Specs approved: 18. Still without final code: syn-001 – syn-003 and syn-014. Coverage: no skew except `two_pointers` 4/18 = 22% (max 20%); Output Limit Exceeded is uncovered. The next 4 specs should include an OLE case and no two-pointer problem. |
| 2026-11-07 | — | — | T-014 | syn-021 (Product of Array Except Self, Output Limit Exceeded, the human's code with debug prints) **approved**, so all statuses are now covered. The human added `prefix_sum` as the 19th algorithm label (D-044): syn-021 is labelled `prefix_sum`, and syn-011's on-track algorithms become `prefix_sum, hash_map`. The `analysis.db` CHECK change is T-014 (migration 0002). `evals/data/` is excluded from ruff, because dataset code is buggy on purpose. Approved specs: 19, 15 with final code. Skew: `two_pointers` 4/19 = 21%. |
| 2026-11-07 | — | — | — | **syn-022** (Longest Consecutive Sequence, TLE, `union_find`) and **syn-023** (Find Median from Data Stream, Wrong Answer, `heap`) approved by the human, with their final code. The code was reformatted to LeetCode's editor shape (class wrapper, indentation), and two comments naming the algorithm were removed (D-043). Both verdicts were checked by running the code: the median is wrong on decreasing input, and the sample answer is right for the TLE. Approved specs: 21, 17 with final code (missing: syn-001 – syn-003, syn-014). With the real sessions, 29 in all, and no skew. |
| 2026-11-07 | — | — | — | The human wrote the final code for syn-001 – syn-003; all three verdicts were checked on LeetCode, with screenshots. syn-002: Wrong Answer **83/88**; the first failing test is nums = [1], target = 0 → [0,0] vs [-1,-1], caused by a first == last shortcut that skips the target check. The story was updated, and `return [first, last]` restored, because the paste had been truncated. syn-003: the code solves **#673 Number of Longest Increasing Subsequence**, not #300; Wrong Answer **19/223**; [1,3,5,4,7] → 4 (a length) vs 2 (a count). The problem, story and counts were updated. **syn-014 removed by the human** and its id retired, so Compile Error is uncovered. Approved specs: 20, all with final code. With the real sessions: 28, no skew. |
| 2026-11-07 | — | — | — | **The human closed the synthetic spec set at 20** (D-045): 20 approved specs, all with LeetCode-checked final code; 28 sessions with the real 8; no skew; known gap: Compile Error. Next: `/pm plan` M2, covering the Anthropic adapter, T-014, the generator and its checks, generation and human review, labelling the real sessions, the split, and the runner. |
| 2026-11-07 | — | — | — | syn-003's on-track algorithms changed to `dynamic_programming` only. The human approved it: for #673, the standard fix is DP over length and count, and the binary-search entry was left over from the #300 version. |
| 2026-11-07 | — | — | T-015 – T-023 | `/pm plan` M2: 10 tasks (T-014 already reserved). The dataset groundwork done ahead of the plan sits in the session log, not as tasks. 28 cases split 19/9. The generator's entry point is the tester's own module, not a `tutor-eval` subcommand (D-046). Blocked on the human: the generator's model id and price (T-015). Not planned: the frozen-copy refresh (later dataset version) and the agent suite (Part 2). |
