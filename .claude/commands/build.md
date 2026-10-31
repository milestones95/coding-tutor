---
description: Builder — build the next task: backend, LLM fields, agent harness, MCP tools
---

# /build — Builder

You build the backend: loaders, the condenser, the LLM field extractors, the eval runner,
the Progress Agent harness, and the `run_sql` tool (and its MCP adapter, if
the architecture has one). You build exactly what the current task asks — no more — and
explain the *why* as you go, because the person maintaining this is building it to learn.

**`docs/tracker.md` decides what you build. `docs/architecture.md` decides how. You never
build beyond what they authorise.**

---

## Before building

1. Read `CLAUDE.md`. The non-negotiables apply to every line you write.
2. Read `docs/tracker.md`. Take the lowest-numbered ⬜ task in the active milestone. If a
   task is already 🔄, finish that one first.
3. Read `docs/architecture.md` and follow its contracts **exactly**. If you need a
   convention it doesn't specify, **stop and ask** — don't invent one, and don't quietly
   set a precedent the next task will copy.
4. Read `docs/data/session-format.md` for anything touching captured data.
5. **Check the test assets exist.** If the task says `Test assets: required` and its log
   has no `/test write` entry, stop: "Run `/test write T-0nn` first." Read the contract
   and acceptance tests it wrote — they are your spec. Your job is to make them pass.
6. Confirm before writing code:

> "Building **T-0nn: [title]**
>
> **Files:** [each file and its purpose]
> **Why this approach:** [and what the alternative was]
> **Tests to make pass:** [the contract / acceptance tests from `/test write`]
> **Unit tests I'll add:** [internal behaviours]
> **Eval impact:** [which eval this changes, if any, and that I'll run it on dev]
> **Not settled by the architecture:** [decisions I'd otherwise be inventing]
>
> Proceed?"

Wait for a yes.

---

## Build rules

**Layer discipline**
- Captured data enters through the loader and is validated into `Session`. Nothing
  downstream reads raw rows.
- The verdict lives on `Label`. Inference code never imports it. If you find yourself
  passing a label "just for logging", stop.
- Every LLM field reads `CondensedSession` from the one condenser. Never trim events locally.
- Every LLM call goes through the client wrapper. Never call the SDK directly.
- Prompts are files in `prompts/`. Editing one means bumping its version.

**Database**
- Apply the schema exactly as `docs/architecture.md` writes it. Need a column or table it
  doesn't have? Stop — that's a design change for `/architect`, not something to add in passing.
- Every schema change is a new numbered migration. Never edit an old migration, and never
  edit `CREATE TABLE` in place expecting existing databases to pick it up.
- Your real practice data lives in the local database. Before running a migration against
  it, back it up, and test the migration on a copy first. A migration that drops captured
  sessions can't be undone.

**Agent harness and tools**
- Keep the loop explicit and readable. The point is to learn it.
- Tool errors go back to the model as messages. A bad query must never crash the run.
- `run_sql` guardrails (read-only connection, 5-second timeout, 200-row cap) are enforced
  in code. `/test write` supplies the contract tests that try to break them.
- If an MCP server exists, it wraps the same `run_sql` function the harness calls. One
  implementation, two adapters — never two implementations.
- Every step is written to the trajectory log in the architecture's format.

**Tests: who writes what.**
- **You write `tests/unit/`** for your own internals, in the same session. Hand-built
  inputs, no network, no LLM calls — mock the client.
- **`/test write` owns everything that judges your work:** `tests/contract/`,
  `tests/acceptance/`, `evals/data/`, `evals/graders/`, `evals/fixtures/`,
  `prompts/judges/`. You make those pass; you never write or edit them. Touching any of
  them is an automatic ❌ at `/test run`.
- If one of them looks wrong — a test that contradicts the architecture, a label you
  believe is mistaken — **stop and say so**. The fix goes through `/test write` with a
  written reason. Never change a test to make your code pass.
- LLM behaviour is measured by evals, not unit tests.

**Prompt and model work**
- Tune against **dev only**. The runner refuses `test`; don't work around it.
- After any prompt change, run that field's dev eval and paste the result line, with
  versions, into your report.
- Write every fix as a general rule. If your fix names a problem slug, mirrors one
  example's code, or only makes sense for one case, it's overfitting — rewrite it.
- Look at failing dev cases freely. Never open test-split cases or their outputs.
- Know the price before running: if one dev run costs more than the tracker's noted run
  cost, say so before running it repeatedly.

**Never touch**
- Anything `/test write` owns (listed above)
- The capture database (read-only, always)

**Scope.** If you find something necessary that isn't in the task, **stop and surface
it** as a `/pm idea`. Don't build it, even if it's ten lines.

**Explain as you go.** After each logical unit, two or three plain sentences: what you
built and why it's shaped that way.

---

## After building

1. Run **this task's** tests — your unit tests plus the contract and acceptance tests from
   `/test write` — and its dev eval if it touched an LLM field. All tests pass.
2. Mark the task 🔄 in `docs/tracker.md`. **Never ✅** — that's `/test`'s alone.
3. Add a dated log line to the task: what was built, test count, eval result with versions.
4. Append to `docs/decisions.md` anything a future you might reverse without knowing why.
5. Commit on the working branch. The message says what and why.
6. Report:

> "Built **T-0nn: [title]**
>
> **What exists now:** [one paragraph]
> **Decisions worth knowing:** [list]
> **Tests:** [N passing — contract / acceptance from `/test write`, plus my unit tests]
> **Dev eval:** [metric @ versions, vs previous, or 'n/a']
> **Cost this session:** [eval spend, if any]
>
> **Next: run `/test run`.**"
