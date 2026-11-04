-- 08_excerpt.sql
-- Why: see what one snapshot's `code` holds (full editor text vs. diff; starter template
-- included?) for a short illustrative excerpt in session-format.md. Read-only.
SELECT ts, length(code), substr(code,1,300) FROM snapshots WHERE session_id LIKE '70241a81%' ORDER BY ts LIMIT 1;
SELECT COUNT(*) FROM sessions WHERE end_reason='accepted';
