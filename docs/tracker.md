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
| M0 | Foundation | ⬜ | One captured session loads, validates, and one logged LLM call runs |
| M1 | Deterministic pieces | ⬜ | Unit tests green on real + hand-built sessions; token budget measured |
| M2 | Dataset + eval runner | ⬜ | Runner writes a versioned result record |
| M3 | Status, algorithm, failure reason | ⬜ | Dev baseline recorded per field |
| M4 | Timeline summary + judge | ⬜ | Judge agreement ≥ 85% recorded |
| M5 | Progress Agent + `run_sql` | ⬜ | One fixture question answered with a logged trajectory |
| M6 | Part 2 evals | ⬜ | All five graders produce a baseline |
| M7 | Model comparison + test split | ⬜ | Comparison table below |

---

## Tasks — active milestone

| ID | Task | Owner | Size | Test assets | Status | Traces to |
|---|---|---|---|---|---|---|
| T-001 | *(created by `/pm plan`)* | build / test | | required / none | ⬜ | |

### T-001 · *title*
**Traces to:** *line in eval-plan.md or architecture.md*
**Done when:** *testable conditions*
**Not included:** *adjacent work this task doesn't do*
**Test assets:** *required / none*
**Log**
- *YYYY-MM-DD `/test write`* — *what was written, counts, what failed as expected*
- *YYYY-MM-DD `/build`* — *what changed, test count, eval result @ versions, commit*
- *YYYY-MM-DD human* — *labels / grades confirmed (test-owned tasks only)*
- *YYYY-MM-DD `/test run`* — *verdict*

---

## Eval baselines (dev)

Every number names its versions. Noise band = spread across 3 runs of the same version.

| Metric | Value | Noise band | Prompt | Model | Dataset | Judge | Date |
|---|---|---|---|---|---|---|---|
| status accuracy | | | | | dev-v1 | — | |
| false "Passed" rate | | | | | dev-v1 | — | |
| failure type accuracy | | | | | dev-v1 | — | |
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
