-- Why: T-001 Done-when 3. After the fix, the human makes three deliberate submits (Accepted,
-- Wrong Answer, Time Limit Exceeded). This lists every captured submit so each can be checked:
-- numeric submission_id, verdict text as LeetCode sent it, test counts, error detail on failures.
-- Read-only:
--   sqlite3 "file:data/capture.db?mode=ro" < scripts/discovery/17_t001_submit_rows.sql
SELECT s.slug,
       j.ts,
       j.status,
       j.tests_passed,
       j.tests_total,
       j.submission_id,
       j.error_detail IS NOT NULL AS has_error_detail,
       j.session_id
FROM judge_events AS j
JOIN sessions AS s ON s.id = j.session_id
WHERE j.kind = 'submit'
ORDER BY j.ts;
