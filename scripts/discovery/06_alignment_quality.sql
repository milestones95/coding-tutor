-- 06_alignment_quality.sql
-- Why: (a) does a snapshot exist at/just before each run, so "snapshot at each run" is
-- possible from stored data; (b) quality: same-slug sessions close together (reload
-- splits?), timezone of attempts.date vs started_at, ended_at vs last activity. Read-only.
.headers on
.mode column
SELECT substr(j.session_id,1,8) sid, j.ts run_ts,
  ROUND((julianday(j.ts) - julianday((SELECT MAX(ts) FROM snapshots s WHERE s.session_id=j.session_id AND s.ts<=j.ts)))*86400,1) secs_since_prev_snap,
  ROUND((julianday((SELECT MIN(ts) FROM snapshots s WHERE s.session_id=j.session_id AND s.ts>j.ts)) - julianday(j.ts))*86400,1) secs_to_next_snap
FROM judge_events j ORDER BY j.ts;
SELECT a.slug, substr(a.session_id,1,8) sid, b_sid, ROUND(gap_min,1) gap_min FROM (
  SELECT slug, id session_id, started_at,
    substr(LAG(id) OVER (PARTITION BY slug ORDER BY started_at),1,8) b_sid,
    (julianday(started_at) - julianday(LAG(COALESCE(ended_at,last_activity_at)) OVER (PARTITION BY slug ORDER BY started_at)))*1440 gap_min
  FROM sessions) a WHERE b_sid IS NOT NULL;
SELECT substr(s.id,1,8) sid, s.started_at, a.date local_date, a.created_at FROM sessions s JOIN attempts a ON a.session_id=s.id WHERE substr(s.started_at,1,10)<>a.date;
SELECT SUM(ended_at IS NULL) null_end, SUM(partial) partial_snaps FROM sessions, (SELECT SUM(partial) partial FROM snapshots);
