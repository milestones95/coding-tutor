-- 10_submit_timing.sql
-- Why: the user reports they submitted (and passed) most sessions, but 0 submits are
-- stored. Check (a) the last recorded event vs. last_activity_at vs. ended_at, to see
-- whether anything after the last Run was ever recorded, (b) orphan judge_events not tied
-- to a session, (c) the submission_id prefix, which shows which LeetCode endpoint was
-- captured. Read-only.
.headers on
.mode column
SELECT s.slug, substr(s.id,1,8) sid,
  (SELECT MAX(ts) FROM judge_events j WHERE j.session_id=s.id) last_run,
  (SELECT MAX(ts) FROM snapshots x WHERE x.session_id=s.id) last_snap,
  s.last_activity_at, s.ended_at,
  ROUND((julianday(s.ended_at)-julianday(s.last_activity_at))*86400,0) end_minus_last_s
FROM sessions s WHERE s.end_reason='ended' ORDER BY s.started_at;
SELECT COUNT(*) orphan_events FROM judge_events WHERE session_id NOT IN (SELECT id FROM sessions);
SELECT substr(submission_id,1,instr(submission_id,'_')) prefix, COUNT(*) FROM judge_events GROUP BY 1;
