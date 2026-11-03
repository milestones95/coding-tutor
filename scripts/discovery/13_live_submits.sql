-- 13_live_submits.sql
-- Why: T-001 finding. The extension code handles submits end to end on paper, so check the
-- extension's live DB (not the Oct 31 copy) for submit rows — especially the human's
-- resubmissions on 2026-11-02 — to tell "submits are dropped at runtime" from "the copy
-- predates a fix". Read-only (mode=ro; the extension may be writing concurrently).
-- Run: sqlite3 'file:/Users/milestucker/dev_work/leetcode-analyzer/data/leetcode.db?mode=ro' < scripts/discovery/13_live_submits.sql
.headers on
.mode column
SELECT kind, COUNT(*) n, MIN(ts) first_ts, MAX(ts) last_ts FROM judge_events GROUP BY kind;
SELECT substr(j.session_id,1,8) sid, s.slug, j.ts, j.kind, j.status, j.tests_passed, j.tests_total, j.submission_id, s.end_reason
FROM judge_events j JOIN sessions s ON s.id=j.session_id WHERE j.kind='submit' ORDER BY j.ts;
SELECT COUNT(*) sessions, MAX(started_at) latest FROM sessions;
SELECT end_reason, COUNT(*) FROM sessions GROUP BY 1;
