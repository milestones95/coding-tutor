"""Keyword-matching baseline for algorithm type (eval plan: "compare against a keyword-matching
baseline"). Tester-owned. A model that can't beat this isn't earning its cost.

Reads only the final code, like the algorithm field (architecture §6.3). Each label has regex cues;
the 1-2 labels with the most cue hits win (ties broken by the list order below). No cue: no label.
"""

import re

VERSION = "keyword-v1"

CUES: dict[str, list[str]] = {
    "heap": [r"\bheapq\b", r"\bheappush\b"],
    "union_find": [r"\bparent\b", r"\bdef find\b"],
    "trie": [r"\bchildren\b", r"\bis_end\b|\bend\b|\bword\b"],
    "graph_topological_sort": [r"\bindegree\b|\bin_degree\b", r"\bprerequisites\b", r"\bgraph\b"],
    "bfs": [r"\bdeque\b", r"\bpopleft\b"],
    "linked_list": [r"\.next\b"],
    "tree_traversal": [r"\.left\b", r"\.right\b"],
    "binary_search": [r"\bmid\b", r"//\s*2", r"\blo\b|\bhi\b"],
    "sliding_window": [r"\bwindow\b", r"\bleft\s*=\s*.+\+\s*1"],
    "two_pointers": [r"\bleft\b|\bL\b|\bslow\b", r"\bright\b|\bR\b|\bfast\b"],
    "prefix_sum": [r"\bprefix\b", r"\bsuffix\b|\brunning\b"],
    "dynamic_programming": [r"\bdp\b", r"\bmemo\b|\bcache\b|\blru_cache\b"],
    "dfs_backtracking": [r"\bdef (dfs|backtrack|can_\w+|has_\w+|traverse)\b", r"\bvisited\b|\bon_path\b"],
    "stack": [r"\bstack\b", r"\.pop\(\)"],
    "intervals": [r"\bintervals\b", r"\bmerged\b"],
    "bit_manipulation": [r"&=?\s*\(?\w+\s*-\s*1", r">>|<<", r"\^"],
    "math": [r"%\s*10\b", r"//\s*10\b"],
    "hash_map": [r"=\s*\{\}", r"\bdict\(|\bset\(|\bdefaultdict\b|\bCounter\b"],
    "greedy": [r"\bgreedy\b"],
}


def predict(code: str) -> list[str]:
    scores = []
    for order, (label, cues) in enumerate(CUES.items()):
        hits = sum(1 for c in cues if re.search(c, code))
        if hits:
            scores.append((-hits, order, label))
    return [label for _, _, label in sorted(scores)[:2]]


class KeywordBaseline:
    """The baseline as a predictor: Session -> {"labels": [...]}, from the final snapshot only."""

    name = "keyword_baseline"
    version = VERSION

    def __call__(self, session) -> dict:
        return {"labels": predict(session.snapshots[-1].code)}
