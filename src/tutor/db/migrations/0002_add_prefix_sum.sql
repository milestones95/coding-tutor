-- 0002_add_prefix_sum.sql — add 'prefix_sum' to the algorithm labels (D-044).
--
-- Existing rows: every session_algorithms row is copied into the rebuilt table unchanged; no row
-- is dropped or edited. SQLite can't alter a CHECK constraint, so the table is rebuilt: create
-- the new table, copy, drop the old one, rename, recreate the index. migrate.py runs the whole
-- file in one transaction, so a failure leaves the database at version 1. Re-running costs
-- nothing (no LLM calls).
CREATE TABLE session_algorithms_new (
  session_id  TEXT NOT NULL REFERENCES session_analysis(session_id),
  label       TEXT NOT NULL CHECK (label IN ('hash_map','two_pointers','sliding_window',
                'binary_search','stack','heap','bfs','dfs_backtracking',
                'dynamic_programming','greedy','intervals','linked_list',
                'tree_traversal','trie','union_find','graph_topological_sort',
                'bit_manipulation','math','prefix_sum')),
  PRIMARY KEY (session_id, label)
);
INSERT INTO session_algorithms_new (session_id, label) SELECT session_id, label FROM session_algorithms;
DROP TABLE session_algorithms;
ALTER TABLE session_algorithms_new RENAME TO session_algorithms;
CREATE INDEX algorithms_label ON session_algorithms(label);
