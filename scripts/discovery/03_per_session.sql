-- 03_per_session.sql
-- Why: per-session size and activity — duration, snapshot count, raw code bytes,
-- run/submit counts, final submit verdict — to judge which sessions are real
-- practice vs. accidental page opens, and to size the condensing problem. Read-only.
.headers on
.mode column
SELECT s.slug, s.end_reason er, s.analysis_status ast,
  ROUND((julianday(s.last_activity_at)-julianday(s.started_at))*1440,1) active_min,
  ROUND((julianday(COALESCE(s.ended_at,s.last_activity_at))-julianday(s.started_at))*1440,1) total_min,
  (SELECT COUNT(*) FROM snapshots x WHERE x.session_id=s.id) snaps,
  (SELECT SUM(length(code)) FROM snapshots x WHERE x.session_id=s.id) code_bytes,
  (SELECT MAX(length(code)) FROM snapshots x WHERE x.session_id=s.id) max_code,
  (SELECT SUM(partial) FROM snapshots x WHERE x.session_id=s.id) partial,
  (SELECT COUNT(*) FROM judge_events j WHERE j.session_id=s.id AND kind='run') runs,
  (SELECT COUNT(*) FROM judge_events j WHERE j.session_id=s.id AND kind='submit') submits,
  (SELECT status FROM judge_events j WHERE j.session_id=s.id AND kind='submit' ORDER BY ts DESC LIMIT 1) last_submit,
  substr(s.id,1,8) sid
FROM sessions s ORDER BY s.started_at;
