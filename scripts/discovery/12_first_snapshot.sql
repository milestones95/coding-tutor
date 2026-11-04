-- 12_first_snapshot.sql
-- Why: decide how much code carry-over affects real sessions. For each real session,
-- compare the first snapshot's size and line count with the final one. A first snapshot
-- close to the final suggests the session began with existing code. Read-only.
.headers on
.mode column
SELECT s.slug, substr(s.id,1,8) sid,
  length(f.code) first_len, length(l.code) final_len,
  length(f.code)-length(replace(f.code,char(10),''))+1 first_lines,
  f.code = l.code first_eq_final
FROM sessions s
JOIN snapshots f ON f.id=(SELECT id FROM snapshots WHERE session_id=s.id ORDER BY ts LIMIT 1)
JOIN snapshots l ON l.id=(SELECT id FROM snapshots WHERE session_id=s.id ORDER BY ts DESC LIMIT 1)
WHERE s.end_reason='ended' ORDER BY s.started_at;
