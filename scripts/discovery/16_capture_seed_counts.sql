-- Why: T-002 seeds data/capture.db from the old capture DB with an SQLite backup. This counts
-- rows per capture table so the seed record (data/capture.seed.json) and the copy can be
-- compared with the source. Run read-only against either file:
--   sqlite3 "file:<db>?mode=ro" < scripts/discovery/16_capture_seed_counts.sql
SELECT 'problems' AS tbl, COUNT(*) AS n FROM problems
UNION ALL SELECT 'sessions', COUNT(*) FROM sessions
UNION ALL SELECT 'snapshots', COUNT(*) FROM snapshots
UNION ALL SELECT 'judge_events', COUNT(*) FROM judge_events
UNION ALL SELECT 'attempts', COUNT(*) FROM attempts
UNION ALL SELECT 'attempt_gaps', COUNT(*) FROM attempt_gaps;
