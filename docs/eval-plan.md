# LeetCode Tutor Agent — Eval Plan

Oct 31, 2026 · @Miles

## Goal and scope

This is a learning project for building an agent harness and evals, not a product. It has two parts, and each one teaches a different pattern:

- **Part 1: Session Analyzer (a workflow).** Fixed steps turn one captured practice session into structured fields. It teaches single-call LLM tasks, labeled datasets, and grading with an LLM judge.
- **Part 2: Progress Agent (an agent).** It answers open-ended questions about my practice history by querying Part 1's data with tools. It teaches the agent loop, tool design, and evals that check the path the agent took.

**Out of scope for now:** an "expected approach" with a code snippet, calling LeetCode's API to run code, multiple users, and UI polish.

## Part 1: Session Analyzer

Code first condenses each captured session. Then it produces seven fields: four come straight from the data, including pass/fail, and three come from the LLM.

**Input:** the problem slug, the event stream, code snapshots, and the final code. The LeetCode verdict is saved at capture time and used as a fact. Verdicts for sessions captured before submit capture worked were backfilled by hand (D-005).

**Condensing step (code, no LLM):** before any LLM call, raw events are collapsed into a short list of meaningful moments:

- A text snapshot of the code every 2 minutes (skipped if nothing changed), plus one at each run and each submit. A 50-minute session tops out around 25 timed snapshots
- Every run and submit with its result and error message
- A change summary for each kept snapshot (lines added/removed, fraction changed, rewrite flag), so big rewrites (new approaches) stand out (D-013)
- Timestamps and elapsed minutes

Every LLM field reads this condensed version. It is stored in the analysis database, where Part 2 reads it with `run_sql` (D-012). How much condensing is needed depends on what the capture tool records (every keystroke vs. periodic snapshots). The raw events stay stored; condensing only decides what the LLM sees.

| Field | Source | Output format |
| --- | --- | --- |
| Problem | LeetCode metadata | Slug, title, difficulty, topic tags |
| Time to finish | Calculated from timestamps | Minutes, from the first event to the final submit (or the last event if never submitted) |
| Attempted at | Capture timestamp | Date. Part 2 needs this for "not seen in a while" |
| Status | LeetCode verdict of the final submit, read by code (D-014); `unknown` when no verdict was captured | One of: Passed · Failed – wrong answer · Failed – too slow · Failed – runtime error · Not submitted · Unknown. The verdict text is mapped by a fixed table (D-019) and also kept verbatim |
| Failure reason | LLM reads the condensed events | One failure type (list below) + a 1–2 sentence explanation |
| Algorithm type | LLM reads the final code | Up to 2 labels from the fixed list below |
| Timeline summary | LLM reads the condensed events | 3–5 sentences: approaches tried, where I got stuck, pivots, final outcome |

**Failure types:** edge case missed · wrong approach · too slow (complexity) · implementation bug · didn't finish · none (passed).

**Algorithm labels:** hash map · two pointers · sliding window · binary search · stack / monotonic stack · heap · BFS · DFS / backtracking · dynamic programming · greedy · intervals · linked list · tree traversal · trie · union find · graph / topological sort · bit manipulation · math.

## Part 1 evals

Start with 30 labeled sessions, measure a baseline, then set targets. The targets below are starting points, not commitments.

**Dataset:** 30 sessions, split 20 dev / 10 test. Mix real sessions from the capture tool with synthetic ones. Cover every failure type and the common algorithms. Real captured data supplies about 8 cases; the rest are synthetic. For each session, I write the algorithm label, the failure type, and a short list of key facts about the timeline.

| Field | Grader | Metric | Starting target |
| --- | --- | --- | --- |
| Failure type | Exact match vs. my label | Accuracy, reported separately for rule-decided and LLM-decided cases | 85% |
| Failure explanation | LLM judge | Consistent with the real failure, no invented causes | 85% |
| Algorithm type | Exact match vs. my label | Accuracy (any overlap with my labels counts). Compare against a keyword-matching baseline | 90% |
| Timeline summary | LLM judge + checklist | % of checklist items met | 85% |
| Condensed events, time to finish, problem, date, status | Unit tests | Exact | 100% |

**Summary checklist:**

- Mentions every approach I tried
- Says where I got stuck
- Names the final approach and outcome
- No invented events
- 5 sentences or fewer

**Condensing step unit tests:**

- Every run and submit is kept, with its result
- There's a snapshot every 2 minutes while the code changes, plus one at each run and each submit
- Elapsed times match the raw timestamps
- A 60-minute session fits a token budget of 16,000 estimated tokens, from the worst measured rate of 253 tokens/min

**Checking the judge:** I hand-grade 20 outputs and measure how often the LLM judge agrees with me. Don't trust judge scores until agreement is at least 85%.

**Tuning rules:**

- Tune on dev only. Run test at milestones.
- If dev is much higher than test, I've overfit. Pull back to more general instructions.
- Write each fix as a general rule, not a patch for one case.
- If I look at a test case's failures, move it into dev and write a replacement.

**Model comparison:** accuracy, cost per session, latency, and consistency (run each case 3 times and check whether the answers change).

## Part 2: Progress Agent

An agent answers open-ended questions about my practice by deciding which queries to run on Part 1's data, one step at a time.

**Example questions:**

- What are my strengths right now?
- What aspects are not interview ready?
- What are my weaknesses?
- What problems have I not seen in a while?

**Data:** one row per session with all Part 1 fields, in a local database (SQLite is enough).

**Tools: raw SQL (decided).**

- **Setup:** one read-only `run_sql` tool with the schema in the system prompt. Most flexible, and teaches query errors and recovery. Guardrails: a read-only connection, a 5-second query timeout, at most 200 rows returned, and SQL errors sent back to the model so it can fix its query.

**Definitions (in the system prompt, draft):**

| Term | Definition |
| --- | --- |
| Struggle | Topic pass rate under 80% over the last 60 days, with at least 3 attempts in that window |
| Strength | Topic pass rate 90% or higher over the last 60 days, with at least 3 attempts in that window, and median solve time at or under target |
| Interview ready | 80%+ pass rate over the last 5 attempts, median medium solve time 25 min or less, attempted in the last 21 days |
| Not seen in a while | No attempt in more than 14 days |

Attempts older than 60 days don't count toward strength or struggle. The agent can still use them for trend questions like "have I improved at DP?"

**Harness:**

- A loop with a 10-step cap
- Tool errors go back to the model as messages, not crashes
- Read-only database access
- Every tool call and result is logged for trajectory evals

## Part 2 evals

Test the agent on a fake practice history with planted patterns, not on Part 1's output. That way the right answers are known, and any mistake is the agent's, not a Part 1 labeling error.

**Fixture database:** about 50 fake sessions with planted patterns:

- Weak at dynamic programming (around 40% pass, mostly "wrong approach")
- Strong at two pointers (95%+ pass, fast)
- Graphs not attempted in 40+ days
- Binary search passes but slowly (mostly "too slow" or long solve times)
- A topic with too few attempts to judge (tests whether the agent says "not enough data")
- Heaps failed often 6+ months ago but passed consistently in the last 60 days (should count as a strength, not a struggle)

**Question set:** about 20 questions, each with an expected answer. Split them into factual questions with one right answer and judgment questions that should surface the planted patterns.

| Grader | What it checks | How |
| --- | --- | --- |
| Exact answer | Factual questions ("what haven't I seen in 30 days") | Compare against the expected set in code |
| Pattern recall | Judgment questions surface the planted patterns | LLM judge with a list of expected findings |
| Grounding | Every number in the answer appears in a tool result | Automated check against the logged tool outputs |
| Trajectory | Queried before answering, recovered from SQL errors, no repeated or pointless queries | Rules on the tool-call log |
| Efficiency | Steps, tokens, cost, latency per question | Logged per run, compared across models |

## Build order

Build the easy, deterministic pieces first and the timeline last, because it's the hardest to label and grade.

1. Lock the session data format, and save the LeetCode verdict at capture time.
2. Build the deterministic pieces: the condensing step, problem, time to finish, attempted at, status.
3. Label 30 sessions and split them into dev and test.
4. Build algorithm type and failure reason, each with its eval. (Status is read from the verdict in step 2.)
5. Build the timeline summary, its judge checklist, and the judge-vs-me agreement check.
6. Seed the fixture database and build the Part 2 agent, harness, and evals.
7. Run the model comparison across both parts.

## Open questions

- [x] Part 2 tools: raw SQL or fixed tools? Decided: raw SQL.
- [ ] Final definitions of "interview ready" and "strength" (the drafts above are placeholders)
- [ ] Aggregate questions like "do I spend too long planning?" need numbers. Add per-session planning / coding / debugging minutes later?
- [x] How do I label "Not submitted" sessions? Decided: status is the verdict; `not_submitted` only once submit capture is reliable, otherwise `unknown` (D-014).
- [x] Where do the synthetic sessions come from? Decided: generated by Claude from specs I write or approve, then reviewed by me before use (D-017).
