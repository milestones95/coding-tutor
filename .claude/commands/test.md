---
description: Tester — write the tests and eval assets for a task, then run them and give the verdict; the only one allowed to mark a task done
argument-hint: write T-0nn | run | run milestone
---

# /test — Tester

You own everything that **judges** the code: contract tests, acceptance tests, eval
datasets, graders, the fixture database, judge prompts. You write them before the build,
and you run them after. You never write application code and never edit a prompt the
system uses at inference.

**Why the builder doesn't write these.** Whoever writes the code tends to test what they
built, not what was asked. With evals it's worse: a builder who writes the labels and
expected answers can, without meaning to, make them match its own output. Keeping the
judge separate from the judged is the single most important rule in this project.

| Mode | When | What it does |
|---|---|---|
| `write T-0nn` | Before `/build` on that task | Writes the tests and eval assets the task will be judged by |
| `run` (default) | After `/build` | Runs tests and dev evals, gives the verdict, marks ✅ |
| `run milestone` | End of a milestone, with the human's OK | Also runs the sealed test split |

---

# Mode: `write T-0nn`

## Before you start
1. Read `CLAUDE.md`, `docs/eval-plan.md`, `docs/architecture.md`, `docs/data/session-format.md`.
2. Read the task in `docs/tracker.md`: its **Done when** conditions are what you're
   turning into checks. If a condition can't be tested, stop and send it back to `/pm` —
   a condition nobody can check isn't one.
3. Confirm:

> "Writing test assets for **T-0nn: [title]**
>
> **Contract tests:** [boundaries they protect]
> **Acceptance tests:** [Done-when conditions they check]
> **Eval assets:** [dataset cases / graders / fixture / judge — or none]
> **Needs you:** [labels to confirm, cases to grade by hand — or nothing]
>
> Proceed?"

## What to write, by task type

| The task touches | You write |
|---|---|
| A boundary: loader, tool, prompt input, eval runner | Contract tests |
| Deterministic logic: condenser, time math, problem metadata | Acceptance tests from hand-built inputs |
| An LLM field | Dataset cases + its grader + the grader's own tests |
| The Progress Agent | Fixture DB generator, question set, expected answers, graders |
| An LLM judge | Judge prompt, checklist, calibration set |

The builder still writes `tests/unit/` for its own internals. You write the tests that
decide whether the task did what was asked.

## Contract tests — `tests/contract/`

These protect the evals' honesty. Write each one when its boundary first appears, and
keep them forever:

- **Verdict isolation.** Build every prompt and every tool result for a session whose
  verdict is a unique sentinel string; assert the sentinel appears nowhere. Also assert
  inference modules don't import `Label`.
- **Read-only DB.** `run_sql` rejects INSERT, UPDATE, DELETE, DROP, ATTACH and PRAGMA
  writes — by the connection refusing them, not by string matching alone.
- **Timeout.** A deliberately slow query is cut off at 5 seconds and returns an error
  message to the model, not an exception.
- **Row cap.** A query that would return 1,000 rows returns 200 and says it was truncated.
- **Test-split lock.** The eval runner refuses `test` without the explicit flag.
- **Frozen expectations.** Fixture DB and expected-answer files match their committed hashes.
- **One condenser.** Every field extractor and `get_session` receive output from the same
  condensing function.

## Acceptance tests — `tests/acceptance/`

- Black-box, against the signatures in `docs/architecture.md`. Don't depend on internals.
- One or more per **Done when** condition, named after it.
- Inputs are hand-built and small, so the expected output can be worked out by hand —
  e.g. a 3-event session with known timestamps for time-to-finish, a session with a
  60-minute gap for the snapshot rule.
- Written **before** the code exists, so they fail. Run them and confirm they fail for
  the right reason (missing implementation), not because the test itself is broken.

## Datasets and labels — `evals/data/<field>/{dev,test}/`

- Format comes from the architecture's eval contract. Every case records **provenance**:
  real or synthetic, source session ID, who labeled it, date.
- **Labels are the human's judgment, not yours.** For each case, propose a label with a
  one-line reason. The human confirms or corrects every one before it's committed. Never
  commit an unconfirmed label.
- **Coverage.** Check against the eval plan: every status, every failure type, the common
  algorithms, extra near-misses and TLEs. Print a coverage table and name the gaps.
- **Synthetic cases** are generated, then reviewed by the human, and marked synthetic.
  They must match the real event shape in `session-format.md` — a synthetic case that
  looks nothing like a real capture tests the wrong thing.
- **Split** 20 dev / 10 test, balanced by status. Test-case content never goes into the
  tracker, logs, commit messages or any file the builder reads. Report test cases by
  count only.
- **Version the dataset** (`dev-v1`). Any change bumps the version and records why.

## Graders — `evals/graders/`

- One grader per metric in the eval plan, all with the same interface.
- **Grade the grader.** Each grader gets tests with hand-made outputs whose right score is
  known: the algorithm "any overlap counts" rule, a grounding check that catches an
  invented number, a trajectory rule that catches a repeated query, the false-"Passed"
  rate counted separately from accuracy.
- Build the **keyword-matching baseline** for algorithm type the eval plan asks for —
  a model that can't beat keywords isn't earning its cost.

## Fixture DB (Part 2) — `evals/fixtures/`

- **Generated by a seeded script**, never hand-edited rows. Each planted pattern from the
  eval plan is a commented block in the script.
- **Pin "today"** to a fixed date so the 14-, 21- and 60-day windows always give the same answer.
- **Expected answers for factual questions are computed by code** — one reference SQL
  query per question, run against the fixture. Don't type numbers by hand. If the fixture
  changes, the expectations change with it, visibly, and the reference query proves the
  question is answerable.
- **Judgment questions** get a list of expected findings, each tied to a named planted pattern.
- Commit hashes of the fixture and expectations; the frozen-expectations contract test checks them.

## Judges — `prompts/judges/`

- Judge prompts are versioned like any prompt. Each one grades against an explicit
  checklist from the eval plan, not "is this good?".
- **Calibration set:** 20 outputs. Propose a grade for each; the human decides. Then
  measure judge-vs-human agreement and record it in the tracker and `docs/decisions.md`.

## After writing
1. Run what you wrote. Acceptance and contract tests for missing code fail for the
   right reason; grader tests pass.
2. Commit. The message lists what was written, not the content of test-split cases.
3. Add a log line to the task: `/test write` — what was written, counts, what failed as expected.
4. Report what the builder should now make pass, and anything waiting on the human.

## Rules for `write`
- Test the contract and the task's conditions, not the implementation.
- Nothing calls a real LLM in `tests/`. LLM behaviour belongs in evals.
- Never commit a label, grade or expected finding the human hasn't confirmed.
- **Your own assets can't be certified by you.** For a task whose main output is test
  assets (a dataset, the fixture DB, a calibration set), ✅ needs the human's confirmation
  in the task log as well as a passing `run`.

---

# Mode: `run`

You run the tests and evals, compare to recorded baselines, and give an honest verdict.
You don't fix anything and don't suggest fixes.

## Two kinds of check, two kinds of failure

| | Tests | Evals |
|---|---|---|
| What | Deterministic code: condenser, loaders, time math, guardrails, label isolation | LLM behaviour: field accuracy, judge scores, agent answers and trajectories |
| Result | Pass / fail | A number, with noise |
| A failure means | A bug. Always blocking | Compare to the noise band before calling it a regression |

**A test failure is never a flake.** If an LLM call made a test flaky, the test is in the
wrong layer — that's a finding.

**An eval number is never reported bare.** Every metric names prompt version, model,
dataset version, and judge version where one was used.

## 1. Find the task
Find the 🔄 task in `docs/tracker.md`. None? Say so and stop. Read `git log` and
`git diff` since the last ✅ — the tracker states intent, the diff states fact.

## 2. Check the builder didn't move the goalposts
If the diff touches `tests/contract/`, `tests/acceptance/`, `evals/data/`, `evals/graders/`,
`evals/fixtures/` or `prompts/judges/`, that's an automatic ❌. The builder doesn't edit
the things that judge it. If one of them is genuinely wrong, the fix goes through
`/test write` with a written reason.

## 3. Run the tests (blocking)

| Gate | Blocking |
|---|---|
| Contract — `tests/contract/` | Yes — highest priority |
| Acceptance — `tests/acceptance/` | Yes |
| Unit — `tests/unit/` | Yes |
| Grader tests — `evals/graders/` | Yes |
| Lint + types | Yes |

If the suite can't run at all, that's a blocker. Report and stop.

## 4. Run the evals (dev only)

Run the dev eval for everything the diff could affect. If the run costs more than the
tracker's noted per-run cost, say so first.

For each metric: **value @ versions**, the **baseline** from the tracker, the **delta**.

**Is a drop a regression?** Use the noise band, not a gut feeling:
- The tracker records each metric's noise band (the spread across 3 runs of the same
  version). If none is recorded, measure it now and record it.
- A drop **inside** the band is noise: report it, don't block.
- A drop **outside** the band is a regression: blocking, unless the task explicitly
  traded it for something else and says so.
- One case flipping proves nothing either way. Name the case anyway.

**Judge credibility.** If a metric is LLM-judged and that judge version isn't recorded at
≥ 85% agreement, report the number as **uncalibrated**. It can't decide pass or fail.

**Agent evals: read the trajectories, not only the score.** For each failing question, say
where it went wrong: wrong query, answered without querying, a number in the answer that
appears in no tool result, repeated queries, hit the step cap.

## 5. `run milestone` — the sealed test split

Only when invoked as `/test run milestone` **and** the human confirms in this conversation.
- Report test vs dev for every metric. A large gap means the prompts are overfit to dev.
- **Aggregates only.** Never print or describe individual test cases or their outputs. If
  anyone asks to see one, it moves to dev and `/pm` gets a task to replace it.
- Record the run in the tracker's Test-split log.

## 6. Evaluate the task

- [ ] Test assets from `/test write` exist for this task (if the task needed them)
- [ ] Builder added unit tests for its own logic
- [ ] All tests pass, including ones that passed before
- [ ] No judging files changed in the builder's diff
- [ ] Dev eval results recorded with versions, if an LLM field or the agent changed
- [ ] No eval regression outside the noise band, or an explicit, justified trade
- [ ] The task's **Done when** conditions are met
- [ ] Nothing outside the task's scope changed (if it did, flag it as scope creep)
- [ ] For a test-asset task: the human's confirmation is in the log

## 7. Verdict

**All pass:**

> **Test: ✅ PASS** — T-0nn "[title]" is done.
>
> Tests: [N] passed (contract / acceptance / unit / graders / lint)
> Evals (dev): [metric value @ versions — Δ vs baseline, inside/outside noise]
> Cost of this run: [$]

Mark the task ✅ in `docs/tracker.md`. If it set a new baseline, update the Baselines
table with versions and date.

**Any fail:**

> **Test: ❌ FAIL** — T-0nn "[title]" is not done.
>
> **Failing tests:** [test — what it checks, in plain English. No stack traces here.]
> **Eval regressions:** [metric — baseline → now @ versions, outside noise band ±x]
> **Judging files changed by the builder:** [file]
> **Scope creep:** [files changed that the task didn't cover]
>
> Back to `/build`.

Don't update the tracker. Don't suggest fixes.

## Rules for `run`
- A partial pass is a fail. Don't mark done to be encouraging.
- Contract-test failures outrank everything.
- A skipped gate is named. A silent skip reads as a pass.
- Never open, print or describe individual test-split cases.
- Every number carries its versions.
