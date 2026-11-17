"""Contract: the 8 test sessions the human unsealed on 2026-11-17 moved to dev in every suite, with their
labels, and nothing else changed split (T-050; CLAUDE.md rule 2; rule 10). Tester-owned
(`/test write T-050`). Kept for the project's life.

`evals/data/split_v2.json` (frozen in the manifest) holds every session's split before the move, written
from the committed dataset-v2 files. Test cases are only counted here, never printed.
"""

import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "evals" / "data"
SUITES = ("failure", "algorithm", "timeline")
MOVED = {f"evals/data/sessions/synthetic/syn-{n}.json" for n in ("009", "013", "018", "023", "025", "027", "029", "030")}
BEFORE = json.loads((DATA / "split_v2.json").read_text())


def _rows(suite, sp):
    return [json.loads(x) for x in (DATA / suite / sp / "cases.jsonl").read_text().splitlines() if x.strip()]


def _ref(row):
    return row["session"].get("synthetic_path") or row["session"]["capture_session_id"]


def test_the_moved_sessions_were_all_in_test_before():
    assert {BEFORE[m] for m in MOVED} == {"test"}


def test_the_moved_sessions_are_in_dev_in_every_suite_and_in_no_test_file():
    for suite in SUITES:
        dev = {_ref(r) for r in _rows(suite, "dev")}
        test = {_ref(r) for r in _rows(suite, "test")}
        assert MOVED <= dev, f"{suite}: {len(MOVED - dev)} moved session(s) not in dev"
        assert not MOVED & test, f"{suite}: a moved session is still in test"


def test_no_other_session_changed_split():
    now = {}
    for suite in SUITES:
        for sp in ("dev", "test"):
            for r in _rows(suite, sp):
                now[_ref(r)] = sp
    assert now.keys() == BEFORE.keys(), "a session was added or dropped"
    changed = [s for s, sp in now.items() if sp != BEFORE[s] and s not in MOVED]
    assert not changed, f"{len(changed)} session(s) changed split outside T-050"


def test_the_moved_cases_keep_their_labels():
    specs = {f"evals/data/sessions/synthetic/{json.loads(x)['id']}.json": json.loads(x)
             for x in (DATA / "sessions/synthetic/specs.jsonl").read_text().splitlines() if x.strip()}
    for r in _rows("failure", "dev"):
        if _ref(r) in MOVED:
            assert r["expected"]["failure_type"] == specs[_ref(r)]["labels"]["failure_type"]
    for r in _rows("algorithm", "dev"):
        if _ref(r) in MOVED:
            assert r["expected"]["labels"] == specs[_ref(r)]["labels"]["algorithms"]


def test_counts_after_the_move():
    for suite in SUITES:
        assert (len(_rows(suite, "dev")), len(_rows(suite, "test"))) == (27, 8), suite
    # every test session left is rule-decided for failure (Accepted, TLE or MLE)
    assert Counter("rule_decided" in r["tags"] for r in _rows("failure", "test")) == Counter({True: 8})


def test_the_specs_agree_with_where_the_sessions_are():
    for x in (DATA / "sessions/synthetic/specs.jsonl").read_text().splitlines():
        s = json.loads(x)
        path = f"evals/data/sessions/synthetic/{s['id']}.json"
        if s["split"] in ("dev", "test"):
            assert s["split"] == BEFORE[path] if path not in MOVED else s["split"] == "dev", s["id"]
