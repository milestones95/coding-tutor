-- 0003_algorithm_labels.sql — the algorithm labels become rows in `algorithm_labels` (D-070, D-050).
--
-- Adds the 20th label, 'sorting'. From now on a new label is one INSERT into algorithm_labels, not
-- a table rebuild.
--
-- Existing rows: every session_algorithms row is copied into the rebuilt table unchanged; no row
-- is dropped or edited (every stored label is one of the 19 the 0002 CHECK allowed, all of which
-- are seeded below). SQLite can't drop a CHECK, so the table is rebuilt: create, copy, drop, rename,
-- recreate the index. migrate.py runs the file in one transaction, so a failure leaves the database
-- at version 2. Re-running costs nothing (no LLM calls).
--
-- Enforcement: `label` REFERENCES algorithm_labels, but SQLite only enforces REFERENCES on a
-- connection that ran `PRAGMA foreign_keys = ON`, and nothing guarantees every connection does.
-- The two triggers refuse an unknown label on any connection (RAISE(ABORT) is a constraint error,
-- sqlite3.IntegrityError in Python), so the guarantee the CHECK gave is kept. Each trigger body sits on
-- one line: migrate.py refuses a line that is only `END;` (it reads as a transaction statement).
CREATE TABLE algorithm_labels (
  label TEXT PRIMARY KEY
);
INSERT INTO algorithm_labels (label) VALUES
  ('hash_map'), ('two_pointers'), ('sliding_window'), ('binary_search'), ('stack'), ('heap'), ('bfs'),
  ('dfs_backtracking'), ('dynamic_programming'), ('greedy'), ('intervals'), ('linked_list'),
  ('tree_traversal'), ('trie'), ('union_find'), ('graph_topological_sort'), ('bit_manipulation'),
  ('math'), ('prefix_sum'), ('sorting');

CREATE TABLE session_algorithms_new (
  session_id  TEXT NOT NULL REFERENCES session_analysis(session_id),
  label       TEXT NOT NULL REFERENCES algorithm_labels(label),
  PRIMARY KEY (session_id, label)
);
INSERT INTO session_algorithms_new (session_id, label) SELECT session_id, label FROM session_algorithms;
DROP TABLE session_algorithms;
ALTER TABLE session_algorithms_new RENAME TO session_algorithms;
CREATE INDEX algorithms_label ON session_algorithms(label);

CREATE TRIGGER session_algorithms_label_insert BEFORE INSERT ON session_algorithms
WHEN NOT EXISTS (SELECT 1 FROM algorithm_labels WHERE label = NEW.label)
BEGIN SELECT RAISE(ABORT, 'unknown algorithm label'); END;

CREATE TRIGGER session_algorithms_label_update BEFORE UPDATE OF label ON session_algorithms
WHEN NOT EXISTS (SELECT 1 FROM algorithm_labels WHERE label = NEW.label)
BEGIN SELECT RAISE(ABORT, 'unknown algorithm label'); END;
