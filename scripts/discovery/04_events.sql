-- 04_events.sql
-- Why: (a) judge_events shape — kinds, statuses, whether error_detail/tests are filled,
-- whether submission_id is set; (b) snapshot cadence — gap between consecutive snapshots,
-- and how often consecutive snapshots are identical; (c) timestamp format. Read-only.
.headers on
.mode column
SELECT kind, status, COUNT(*) n, SUM(error_detail IS NOT NULL AND error_detail<>'') has_err,
  SUM(tests_total IS NOT NULL) has_tests, SUM(submission_id IS NOT NULL) has_subid,
  GROUP_CONCAT(DISTINCT language) langs
FROM judge_events GROUP BY 1,2;
SELECT substr(session_id,1,8) sid, ts, kind, status, tests_passed, tests_total, runtime, memory,
  substr(replace(error_detail,char(10),' | '),1,70) err, submission_id
FROM judge_events ORDER BY ts;
-- snapshot gaps
WITH g AS (
  SELECT session_id, ts, code,
    (julianday(ts)-julianday(LAG(ts) OVER (PARTITION BY session_id ORDER BY ts)))*86400 gap_s,
    code = LAG(code) OVER (PARTITION BY session_id ORDER BY ts) same
  FROM snapshots)
SELECT COUNT(gap_s) gaps, ROUND(MIN(gap_s),2) min_s, ROUND(AVG(gap_s),2) avg_s, ROUND(MAX(gap_s),1) max_s,
  SUM(gap_s<2) lt2s, SUM(gap_s BETWEEN 2 AND 10) s2_10, SUM(gap_s>10 AND gap_s<=60) s10_60, SUM(gap_s>60) gt60,
  SUM(same) identical_to_prev
FROM g;
SELECT language, COUNT(*) FROM snapshots GROUP BY 1;
