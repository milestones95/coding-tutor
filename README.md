# SDLC commands — LeetCode Tutor Agent

Four Claude Code slash commands, one shared rules file, and a tracker template. Together
they run the build of the Session Analyzer (Part 1) and Progress Agent (Part 2) from
`docs/eval-plan.md`.

## Install

```
your-repo/
├── CLAUDE.md                      ← shared non-negotiables, read by every agent
├── .claude/commands/
│   ├── architect.md               → /architect
│   ├── pm.md                      → /pm
│   ├── build.md                   → /build
│   └── test.md                    → /test
└── docs/
    ├── eval-plan.md               ← export your Eval Plan doc here as markdown
    └── tracker.md                 ← template; /pm fills it in
```

The filename becomes the command name. You can also move each file to
`.claude/skills/<name>/SKILL.md` if you prefer the skills layout — the content works as is.

## The four agents

| Command | Role | Writes code? | Can mark done? |
|---|---|---|---|
| `/architect [data\|review]` | Profiles the real capture data, then writes the architecture doc | No | No |
| `/pm plan \| idea "…" \| review` | Creates tasks, guards scope, reconciles the tracker with git | No | No — can only move things backwards |
| `/build` | Builds one task: backend, LLM fields, eval runner, agent harness, `run_sql` / MCP. Writes only its own unit tests | Yes | No |
| `/test write T-0nn` | Writes what the task is judged by: contract and acceptance tests, eval datasets (you confirm labels), graders, fixture DB, judges | Tests and eval assets only | No |
| `/test run [milestone]` | Runs tests + dev evals, compares to baselines, gives the verdict | No | **Yes — only this one** |

Order: `/architect` → `/pm plan` → (`/test write` → `/build` → `/test run`) per task →
`/pm review` at the end of each session. Any new idea, from you or an agent, goes through `/pm idea` first.

## How the nine example commands mapped

| Example | Here | Why |
|---|---|---|
| `/vision` | Dropped | Your eval plan already is the vision doc |
| `/data-discovery` | Phase 1 of `/architect` | Profiles the capture DB instead of a warehouse |
| `/page-prd` | Dropped | No pages; each field's spec already lives in the eval plan |
| `/arch-review` | `/architect` phase 2 | Standard rewritten for LLM pipelines and agent harnesses |
| `/build` | `/build` | Same discipline; finance rules swapped for eval-integrity rules |
| `/regression` | `/test` | Adds evals, noise bands, judge calibration, sealed test split |
| `/ui-review`, `/design-pass` | Dropped | UI polish is out of scope |
| `/sprint-review` | `/pm review` | Merged with task creation; adds a scope-health check |

## What the rules protect

The finance commands guarded against "a wrong number rendered confidently". The
equivalent here is **an eval score you can't trust**. Most of the rules exist to stop that:

- the LeetCode verdict leaking into a model input
- tuning on the test split, or peeking at it
- a judge whose scores were never checked against your own grading
- an expected answer edited to make a failing eval pass
- the builder writing the tests, labels or expected answers that grade its own work
- eval numbers with no record of which prompt, model and dataset produced them
- a one-case wobble mistaken for a regression (or a real regression waved off as noise)

The scope rules — `/pm idea`, no task without a trace to the eval plan, no L-sized tasks,
the Deferred list with triggers — are there for the other risk you named: the project
getting bloated.
