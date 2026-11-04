-- 15_live_latest.sql
-- Why: T-001. The human just submitted coin-change again (submission 2188137392, Accepted,
-- task_finish_time 1793659898539). Check whether that submit, or anything from that visit,
-- reached the live DB. Read-only (mode=ro).
.headers on
.mode column
SELECT substr(s.id,1,8) sid, s.slug, s.started_at, s.last_activity_at, s.ended_at, s.end_reason,
  (SELECT COUNT(*) FROM snapshots x WHERE x.session_id=s.id) snaps,
  (SELECT COUNT(*) FROM judge_events j WHERE j.session_id=s.id) judge
FROM sessions s WHERE s.started_at >= '2026-11-02T21:00' ORDER BY s.started_at;
SELECT COUNT(*) submits, (SELECT MAX(ts) FROM snapshots) latest_snapshot FROM judge_events WHERE kind='submit';
