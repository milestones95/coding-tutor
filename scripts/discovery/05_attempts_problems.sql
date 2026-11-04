-- 05_attempts_problems.sql
-- Why: attempts/attempt_gaps look like output of an earlier analyzer, not capture data.
-- Check what they hold (status, verdict_reason, source, confidence) and whether they
-- would leak a verdict-like label. Also check problem metadata coverage for slugs
-- that have sessions (title, difficulty, tags, description). Read-only.
.headers on
.mode column
SELECT substr(session_id,1,8) sid, slug, date, status, time_taken_min, category, approach_pattern,
  confidence, source, created_at, substr(verdict_reason,1,60) verdict_reason
FROM attempts ORDER BY created_at;
SELECT a.slug, g.tag, substr(g.detail,1,60) detail FROM attempt_gaps g JOIN attempts a ON a.id=g.attempt_id LIMIT 6;
SELECT COUNT(*) total, SUM(description IS NOT NULL) has_desc, SUM(difficulty IS NOT NULL) has_diff,
  SUM(tags<>'[]') has_tags, SUM(category IS NOT NULL) has_cat, MIN(updated_at), MAX(updated_at) FROM problems;
SELECT p.slug, p.frontend_id, p.title, p.difficulty, p.tags, p.category, length(p.description) desc_len
FROM problems p WHERE p.slug IN (SELECT slug FROM sessions);
SELECT category, COUNT(*) FROM problems GROUP BY 1 ORDER BY 2 DESC LIMIT 25;
