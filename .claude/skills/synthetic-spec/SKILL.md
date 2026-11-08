---
name: synthetic-spec
description: Draft specs for synthetic practice sessions, the labels the Part 1 evals grade against. Use when the human wants to create, extend or review synthetic-session specs (problem, verdict, failure type, algorithms, approaches, course correction, key facts), or asks what coverage the dataset still needs.
---

# synthetic-spec — draft synthetic-session specs

A **spec** describes one made-up practice session: which problem, what you tried, how it
ended. It is the **label**. The eval grades the model's failure type, algorithm labels and
timeline summary against it (architecture §8.5, D-017). A separate generator later writes the
code snapshots and run output that make the spec's story visible. This skill only writes specs.

**The human decides every label (CLAUDE.md rule 11).** You draft and propose; the human
confirms or corrects each spec before it counts. Never move a spec into `specs.jsonl` without
the human's explicit approval of that spec in this conversation.

## Files

| File | Holds | Committed |
|---|---|---|
| `evals/data/sessions/synthetic/specs.draft.jsonl` | specs you drafted, not yet approved | no, until approved |
| `evals/data/sessions/synthetic/specs.jsonl` | specs the human approved: the label source | yes, after approval |

One JSON object per line. IDs run `syn-001`, `syn-002`, … across both files and never reuse.

## The spec format

```json
{"id": "syn-014", "split": "unassigned",
 "problem": {"slug": "coin-change", "title": "Coin Change", "difficulty": "Medium",
             "tags": ["array", "dynamic-programming", "breadth-first-search"]},
 "language": "python3", "duration_min": 18, "runs": 4,
 "verdict": {"status": "Time Limit Exceeded", "tests_passed": 41, "tests_total": 63},
 "labels": {"failure_type": "too_slow", "algorithms": ["dynamic_programming"]},
 "story": {"approaches": ["plain recursion over every coin", "recursion with a memo dict"],
           "course_correction": {"first_approach_on_track": false, "corrected": true, "at_min": 9},
           "final_approach": "top-down recursion with a memo dict; deep recursion still too slow on large amounts",
           "on_track_algorithms": ["dynamic_programming"]},
 "key_facts": ["the first two runs time out on the sample tests", "a memo dict appears around minute 9",
               "the final submit times out at 41/63"]}
```

## Inputs to collect (ask for what the human didn't give)

1. **Problem**: a real LeetCode slug or title. Always fill `problem` from the capture DB, never
   from memory:
   `uv run python .claude/skills/synthetic-spec/scripts/problem_meta.py <slug or title words>`
2. **Verdict** of the final submit: LeetCode's exact text, or `null` if never submitted.
   `Accepted` · `Wrong Answer` · `Time Limit Exceeded` · `Memory Limit Exceeded` · `Runtime Error` ·
   `Compile Error` · `Output Limit Exceeded`. Test counts must be plausible for the problem. A
   failing verdict never has every test passing; Accepted always does; Compile Error passes 0.
3. **Failure type**: `edge_case_missed` · `wrong_approach` · `too_slow` · `implementation_bug` ·
   `did_not_finish` · `none`. Fixed by the verdict in two cases (the pipeline applies these as rules):
   - Accepted ⇒ `none`, and only Accepted is `none`;
   - Time / Memory Limit Exceeded ⇒ `too_slow`.

   For anything else, it is the human's judgment of *why* it failed:
   - `edge_case_missed`: the idea is right, a corner case breaks it (empty input, duplicates,
     overflow, off-by-one at a boundary);
   - `wrong_approach`: the idea itself can't solve the problem (e.g. greedy where DP is needed);
   - `implementation_bug`: right idea, broken code (wrong index, typo, crash);
   - `did_not_finish`: gave up or ran out of time, often with no submit.
4. **Algorithms**: 1–2 labels describing **what the final code does**, not what the problem
   ideally needs. A wrong greedy attempt at a DP problem is labelled `greedy`. Use labels from:
   `hash_map` `two_pointers` `sliding_window` `binary_search` `stack` `heap` `bfs` `dfs_backtracking`
   `dynamic_programming` `greedy` `intervals` `linked_list` `tree_traversal` `trie` `union_find`
   `graph_topological_sort` `bit_manipulation` `math` `prefix_sum` (prefix sums or products, D-044).
5. **Approaches**: every distinct approach, in the order tried, in plain words. A refinement
   (fixing a bug in the same idea) is not a new approach.
6. **Course correction** (D-026):
   - first approach on track: `{"first_approach_on_track": true, "corrected": null, "at_min": null}`
   - off track, switched: `{"first_approach_on_track": false, "corrected": true, "at_min": <minute>}`
   - off track, never switched: `{"first_approach_on_track": false, "corrected": false, "at_min": null}`
7. **Final approach**: one sentence on what the last code does, and why it passed or failed.
   **On-track algorithms** (`story.on_track_algorithms`, D-039): when the first approach was off
   track, 1–2 labels for what *would* have worked. It makes "off track" a checkable claim. Use
   `null` when the first approach was on track. Labels only, never code: the eval plan rules out an
   expected approach with code. It is never shown to a model. `wrong_approach` always means the
   first approach was off track; a switch to another idea that also fails is still `wrong_approach` (D-063).
8. **Language**: `python3` only for now (D-042). A Python *Compile Error* on LeetCode means a
   `SyntaxError`/`IndentationError`; a misspelt name is a Runtime Error.
   **Shape**: `duration_min` (2–60, usually 10–30) and `runs` (0–20), consistent with the story. A course
   correction needs time before and after it; a near-miss usually has several runs.
9. **Key facts**: 2–4 things a correct timeline summary must mention, each **visible in the
   session's behaviour** (a run result, when code changed shape, the final verdict). They should
   not be opinions or labels.
10. **Split**: leave `"unassigned"`. Specs are split 20 dev / 10 test, balanced by status, only
    when the dataset is assembled.

## Variety: don't let the dataset lean one way (D-040)

A metric measured on a lopsided dataset measures the common case. Mostly-Accepted sessions let a
model score well by always saying "passed"; all-short sessions never test long timelines. Spread
the specs across every dimension, and lean **away** from where the real sessions already sit.

| Dimension | Rule (over the whole dataset, real + synthetic) |
|---|---|
| Verdict / status | no one status above 35%; cover every status, including never-submitted |
| Failure type | no one type above 30%; cover all six |
| Difficulty | reported, not balanced: Hard problems are rare in practice (D-041) |
| Time spent | most sessions 10–30 min; at least one under 10 and at least one over 30 (D-041) |
| Algorithm | no one label on more than 20% of sessions |
| Problem | a synthetic spec never reuses a problem, real or synthetic |
| First approach | a mix of on track, corrected and not corrected |

**The real sessions skew** (frozen copy, 8 sessions): 7 Accepted, nothing over 25 minutes, two
problems seen twice. So synthetic specs should be mostly failing verdicts, mostly 10–30 minutes,
and include at least one session over 30 minutes.

Always check balance with the real sessions counted:
`uv run python evals/generate/check_specs.py --with-real evals/data/sessions/synthetic/specs*.jsonl`
It prints the distribution with percentages and a `skew` line for each rule broken, from 8
sessions on. Before drafting the next batch, read the skew lines and aim the new specs at them.
When proposing a batch, say which skew lines it fixes.

## Workflow

1. **Plan coverage first** when drafting a batch. Run the checker over what exists and fill the
   reported gaps:
   `uv run python evals/generate/check_specs.py --with-real evals/data/sessions/synthetic/specs*.jsonl`
   Across the whole dataset (real plus synthetic, about 30 cases), aim for:
   - every failure type;
   - every status, including runtime error, output limit and never-submitted;
   - near-misses (≥ 90% of tests passing);
   - a few sessions where the first approach was already right, to catch invented course
     corrections;
   - corrected and not-corrected sessions;
   - a spread of algorithms and difficulties.
2. **Draft** each spec, appending it to `specs.draft.jsonl`.
3. **Check**: run the checker (with `--with-real`) on the draft and approved files. Fix every
   ERROR before showing the human. Mention warnings, and say how the batch moved the skew lines.
4. **Show the human** each spec as a short table (problem · verdict · failure type · algorithms
   · approaches → final · course correction · key facts), with a one-line reason for each label.
   Ask them to confirm or correct each one.
5. **On approval only**, move the approved specs from `specs.draft.jsonl` to `specs.jsonl` and
   re-run the checker on `specs.jsonl`. Note in the tracker's dataset task log: how many were
   approved, by the human, on what date. Report counts, not the content of any spec later
   assigned to `test`.

## Don'ts

- Don't invent problem metadata. Use the lookup script.
- Don't put code in a spec. The generator writes code, from the story.
- Don't make every story clean. Real sessions have false starts and refinements, and some never
  finish.
- Don't write a key fact that names a label ("used dynamic programming"). Describe what's visible
  ("a 2-D table appears at minute 6").
