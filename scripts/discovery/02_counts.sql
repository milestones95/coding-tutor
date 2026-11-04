-- 02_counts.sql
-- Why: row counts per table, session key format, time range covered, and the
-- distribution of end_reason / analysis_status. Read-only.
.headers on
.mode column
SELECT 'problems' t, COUNT(*) n FROM problems UNION ALL
SELECT 'sessions', COUNT(*) FROM sessions UNION ALL
SELECT 'snapshots', COUNT(*) FROM snapshots UNION ALL
SELECT 'judge_events', COUNT(*) FROM judge_events UNION ALL
SELECT 'attempts', COUNT(*) FROM attempts UNION ALL
SELECT 'attempt_gaps', COUNT(*) FROM attempt_gaps;
SELECT id, slug, started_at, last_activity_at, ended_at, end_reason, analysis_status FROM sessions ORDER BY started_at LIMIT 5;
SELECT MIN(started_at), MAX(started_at), COUNT(DISTINCT slug) distinct_slugs FROM sessions;
SELECT end_reason, analysis_status, COUNT(*) FROM sessions GROUP BY 1,2 ORDER BY 3 DESC;
SELECT length(id) idlen, COUNT(*) FROM sessions GROUP BY 1;
