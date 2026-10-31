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
