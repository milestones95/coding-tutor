-- 09_carryover.sql
-- Why: the 70241a81 two-sum session's first snapshot is already a full solution.
-- Check whether a session's first snapshot equals the previous same-slug session's last
-- snapshot (LeetCode restores saved editor code), which would make "approaches tried"
-- and time-to-finish misleading for repeat attempts. Read-only.
.headers on
.mode column
WITH f AS (SELECT session_id, code FROM snapshots s WHERE ts=(SELECT MIN(ts) FROM snapshots WHERE session_id=s.session_id)),
     l AS (SELECT session_id, code FROM snapshots s WHERE ts=(SELECT MAX(ts) FROM snapshots WHERE session_id=s.session_id)),
     seq AS (SELECT id, slug, started_at, LAG(id) OVER (PARTITION BY slug ORDER BY started_at) prev FROM sessions)
SELECT seq.slug, substr(seq.id,1,8) sid, substr(seq.prev,1,8) prev_sid, length(f.code) first_len,
  (SELECT length(code) FROM l WHERE l.session_id=seq.prev) prev_last_len,
  f.code = (SELECT code FROM l WHERE l.session_id=seq.prev) starts_with_prev_final
FROM seq JOIN f ON f.session_id=seq.id WHERE seq.prev IS NOT NULL;
