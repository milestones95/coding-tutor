-- 14_live_today.sql
-- Why: T-001 finding. The human submitted coin-change (Accepted, 191/191) at ~5:30 PM ET
-- on 2026-11-02 (screenshot). See what the live DB recorded for today's sessions — snapshots,
-- runs, timing — to locate where the submit result was lost. Read-only (mode=ro).
.headers on
.mode column
SELECT substr(s.id,1,8) sid, s.slug, s.started_at, s.last_activity_at, s.ended_at, s.end_reason,
  (SELECT COUNT(*) FROM snapshots x WHERE x.session_id=s.id) snaps,
  (SELECT COUNT(*) FROM judge_events j WHERE j.session_id=s.id) judge
FROM sessions s WHERE s.started_at >= '2026-11-02' ORDER BY s.started_at;
SELECT substr(session_id,1,8) sid, ts, kind, status, tests_passed, tests_total, submission_id
FROM judge_events WHERE ts >= '2026-11-02' ORDER BY ts;
SELECT substr(session_id,1,8) sid, ts, length(code) len FROM snapshots
WHERE ts >= '2026-11-02T21:20' ORDER BY ts;
