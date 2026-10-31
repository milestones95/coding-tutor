# LeetCode Tutor Agent — Project Rules

> Every coding agent in this repo reads this file first. It holds the non-negotiables.
> The commands in `.claude/commands/` hold the workflow. If the two ever disagree, this
> file wins and the disagreement gets raised with the human.

## What this project is

A **learning project** for building an agent harness and evals. It is not a product.
Success is measured by what was learned and whether the evals are trustworthy, not by
feature count.

- **Part 1 — Session Analyzer (workflow).** Turns one captured practice session into
  structured fields: problem, time to finish, attempted at, status, failure reason,
  algorithm type, timeline summary.
- **Part 2 — Progress Agent (agent).** Answers open-ended questions about practice history
  by running read-only SQL over Part 1's data, one step at a time.

`docs/eval-plan.md` is the requirements document. If something is not in it, it is not a
requirement yet.

## The workflow

| Step | Command | Who | Produces |
|---|---|---|---|
| 1 | `/architect` | Architect | `docs/data/session-format.md`, `docs/architecture.md` |
| 2 | `/pm plan` | Project manager | Tasks in `docs/tracker.md` |
| 3 | `/test write T-0nn` | Tester | Contract + acceptance tests and eval assets the task is judged by |
| 4 | `/build` | Builder | Code + its own unit tests, marked 🔄 |
| 5 | `/test run` | Tester | ✅ Done or ❌ back to the builder |
| — | `/test run milestone` | Tester | Sealed test-split results, aggregates only |
| — | `/pm idea "<idea>"` | Project manager | A scope decision, written down |
| — | `/pm review` | Project manager | A tracker that matches the code |

Loop 3 → 5 for each task until the milestone closes. Run `/pm review` at the end of each working session.

## Non-negotiables

1. **The LeetCode verdict is an eval label, never a model input.** It is saved at capture
   time and used only by graders. No prompt builder, tool, or agent context may read it.
   A test enforces this. If a task seems to need the verdict at inference time, the task
   is wrong — stop and raise it.
2. **The test split is sealed.** Only `/test` reads `evals/data/*/test/`, and only at a
   milestone the human has approved. Builders tune on dev. If anyone looks at a test case's
   failure details, that case moves to dev and gets a replacement.
3. **Condensed events are defined once.** Every LLM field and Part 2's `get_session` read
   the same condensing function. No field gets its own private view of raw events.
4. **The Progress Agent's database access is read-only**, enforced by the connection, not
   by the prompt. Query timeout and row cap are enforced in code.
5. **Every LLM call goes through one client wrapper** that logs model, prompt version,
   tokens, cost, latency, and a run ID. No direct SDK calls elsewhere.
6. **Prompts live in files, versioned.** A prompt edit is a code change: it gets a commit
   and an eval run on dev.
7. **Every eval number names its versions.** `status acc 0.87 @ prompt status-v4, model X,
   dataset dev-v2, judge v1` — never a bare `0.87`. A number without versions cannot be
   compared with the next one.
8. **No judge score counts until the judge is calibrated** (≥ 85% agreement with
   hand-graded labels, recorded in `docs/decisions.md`).
9. **Fix rules, not cases.** A prompt fix must be a general instruction, never a patch
   that names or mirrors one dataset example.
10. **Fixture data and expected answers are frozen.** Changing an expected label or a
    planted pattern needs a written reason in the task. Editing an expectation to make a
    failing eval pass defeats the eval.
11. **No agent marks its own work done, and no agent writes the tests that judge it.**
    `/test write` owns `tests/contract/`, `tests/acceptance/`, `evals/data/`,
    `evals/graders/`, `evals/fixtures/` and `prompts/judges/`; the builder only writes
    `tests/unit/`. Only `/test run` sets ✅. Labels, hand grades and expected findings are
    the human's call — agents propose, the human confirms.
12. **Scope is guarded.** Anything not in the tracker goes through `/pm idea` first. Small
    and obviously useful is not an exception — that is exactly how scope creeps.

## Out of scope (from the eval plan)

An "expected approach" with code, running code through LeetCode's API, multiple users,
UI polish. A dashboard is out of scope unless the tracker says otherwise.

## Where things live

| Path | Contains | Never contains |
|---|---|---|
| `docs/eval-plan.md` | What to build and how to evaluate it | Task status |
| `docs/architecture.md` | How it is built — contracts, layout, conventions | Task status |
| `docs/data/session-format.md` | What the capture tool actually records | Guesses |
| `docs/tracker.md` | **All** task status, eval baselines, session log | Design decisions |
| `docs/decisions.md` | Append-only decisions, each with its reason or measurement | Task status |
| `tests/unit/` | Builder's tests of its own internals | LLM calls |
| `tests/contract/`, `tests/acceptance/` | Tester's checks of boundaries and Done-when conditions | Anything the builder wrote |
| `evals/` | Datasets, graders, fixtures, eval results — tester-owned | Application code |
| `prompts/` | Versioned prompt files | Logic |
