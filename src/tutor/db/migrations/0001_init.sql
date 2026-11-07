-- 0001_init.sql — the analysis.db schema, exactly as docs/architecture.md §3.2 writes it.
--
-- Existing rows: none. This is the first migration and creates every table on an empty file.
-- analysis.db is derived data, so any later migration may rebuild its tables from capture.db:
-- timelines and the deterministic `sessions` facts cost nothing to rebuild; LLM fields
-- (session_analysis, session_algorithms, field_provenance) cost a re-run of their calls (§3.3).
-- Never edit this file once applied; a schema change is a new NNNN_<name>.sql.
CREATE TABLE schema_migrations (
  version     INTEGER PRIMARY KEY,
  name        TEXT    NOT NULL,
  applied_at  TEXT    NOT NULL              -- ISO-8601 UTC
);

CREATE TABLE problems (
  slug        TEXT PRIMARY KEY,
  title       TEXT NOT NULL,
  difficulty  TEXT NOT NULL CHECK (difficulty IN ('Easy','Medium','Hard')),
  tags        TEXT NOT NULL DEFAULT '[]'    -- JSON array of LeetCode tag slugs
);

CREATE TABLE sessions (
  session_id            TEXT PRIMARY KEY,   -- capture sessions.id (UUID)
  slug                  TEXT NOT NULL REFERENCES problems(slug),
  attempted_at_utc      TEXT NOT NULL,      -- ISO-8601 UTC, first event
  attempted_date_local  TEXT NOT NULL,      -- YYYY-MM-DD in config timezone
  time_to_finish_min    REAL NOT NULL,      -- 1 decimal
  status                TEXT NOT NULL CHECK (status IN ('passed','failed_wrong_answer',
                          'failed_too_slow','failed_output_limit','failed_runtime_error',
                          'not_submitted','unknown')),
  leetcode_verdict      TEXT,               -- raw verdict of the final submit; NULL if none
  tests_passed          INTEGER,            -- final submit
  tests_total           INTEGER,            -- final submit
  status_source         TEXT NOT NULL CHECK (status_source IN
                          ('capture_submit','human_resubmit','no_submit','not_captured')),
  run_count             INTEGER NOT NULL,
  submit_count          INTEGER NOT NULL,   -- captured submits
  loaded_at             TEXT NOT NULL
);
CREATE INDEX sessions_date ON sessions(attempted_date_local);
CREATE INDEX sessions_slug ON sessions(slug, attempted_date_local);
CREATE INDEX sessions_status ON sessions(status);

CREATE TABLE condensed_timelines (
  session_id         TEXT PRIMARY KEY REFERENCES sessions(session_id),
  condenser_version  TEXT    NOT NULL,     -- e.g. 'c1'
  timeline_json      TEXT    NOT NULL,     -- CondensedSession.model_dump_json()
  rendered_text      TEXT    NOT NULL,     -- render(condensed) — what prompts receive
  est_tokens         INTEGER NOT NULL,     -- len(rendered_text) // 4
  truncated          INTEGER NOT NULL CHECK (truncated IN (0,1)),
  built_at           TEXT    NOT NULL
);

CREATE TABLE session_analysis (
  session_id           TEXT PRIMARY KEY REFERENCES sessions(session_id),
  failure_type         TEXT CHECK (failure_type IN ('edge_case_missed','wrong_approach',
                         'too_slow','implementation_bug','did_not_finish','none')),
  failure_type_source  TEXT CHECK (failure_type_source IN ('rule','llm')),
  failure_explanation  TEXT,
  timeline_summary     TEXT,
  condenser_version    TEXT NOT NULL,      -- version of the timeline the fields read
  updated_at           TEXT NOT NULL
);
CREATE INDEX analysis_failure ON session_analysis(failure_type);

CREATE TABLE session_algorithms (
  session_id  TEXT NOT NULL REFERENCES session_analysis(session_id),
  label       TEXT NOT NULL CHECK (label IN ('hash_map','two_pointers','sliding_window',
                'binary_search','stack','heap','bfs','dfs_backtracking',
                'dynamic_programming','greedy','intervals','linked_list',
                'tree_traversal','trie','union_find','graph_topological_sort',
                'bit_manipulation','math')),
  PRIMARY KEY (session_id, label)
);
CREATE INDEX algorithms_label ON session_algorithms(label);

CREATE TABLE field_provenance (
  session_id      TEXT NOT NULL REFERENCES sessions(session_id),
  field           TEXT NOT NULL CHECK (field IN ('failure','algorithm','timeline_summary')),
  prompt_name     TEXT NOT NULL,
  prompt_version  TEXT NOT NULL,
  provider        TEXT NOT NULL,
  model           TEXT NOT NULL,
  run_id          TEXT NOT NULL,
  call_id         TEXT NOT NULL,          -- joins to logs/llm_calls.jsonl
  created_at      TEXT NOT NULL,
  PRIMARY KEY (session_id, field)
);
