-- 01_inventory.sql
-- Why: Phase 1 step 1 — learn what tables exist, their DDL, and row counts before
-- designing anything against the capture format. Read-only.
-- Run: sqlite3 'file:data/reference/capture.db?immutable=1' < scripts/discovery/01_inventory.sql
-- (immutable=1 because the db files are read-only on disk and the WAL is empty.)
.headers on
.mode column
SELECT type, name, tbl_name FROM sqlite_master ORDER BY type, name;
.schema
