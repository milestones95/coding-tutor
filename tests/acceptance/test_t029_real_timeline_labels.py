"""Acceptance tests for T-029: timeline labels for the 8 real sessions (eval plan "Summary checklist";
architecture §8.1 `timeline` expected). Tester-owned (`/test write T-029`, 2026-11-08).

Each real session in `evals/data/sessions/real/labels.jsonl` gains the two checklist parts the
synthetic specs already have:
    story.approaches       every distinct approach, in the order tried, plain words (≥ 1)
    story.final_approach   one sentence: what the last code does and how it ended
They are the human's labels (rule 11): the tester proposes from the session, the human confirms.
The two sessions in the sealed test split are written by the human without the tester opening them.

What T-020 already settled (labels, course_correction, on_track_algorithms, key_facts) must not
move: its content is pinned below by hash. Changing it needs a written reason in the task (rule 10)
and a new pin.
"""

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LABELS = REPO / "evals" / "data" / "sessions" / "real" / "labels.jsonl"
T020_PIN = "d1ee3acc563ba292170e8d6a50ed6a0c2e017de9bc8ccf801e2fed68d7c95808"


def _rows():
    return [json.loads(line) for line in LABELS.read_text().splitlines() if line.strip()]


def test_all_eight_real_sessions_are_labelled():
    assert len(_rows()) == 8


def test_every_real_session_lists_its_approaches_in_plain_words():
    missing = [r["slug"] for r in _rows()
               if not (isinstance(r["story"].get("approaches"), list) and r["story"]["approaches"]
                       and all(isinstance(a, str) and a.strip() for a in r["story"]["approaches"]))]
    assert not missing, f"{len(missing)} real session(s) have no story.approaches"


def test_every_real_session_names_its_final_approach():
    missing = [r["slug"] for r in _rows()
               if not (isinstance(r["story"].get("final_approach"), str) and r["story"]["final_approach"].strip())]
    assert not missing, f"{len(missing)} real session(s) have no story.final_approach"


def test_a_course_correction_means_at_least_two_approaches():
    """The checklist asks whether the first approach was on track and whether it changed. A session
    labelled 'corrected' with one approach contradicts itself."""
    bad = [r["slug"] for r in _rows()
           if r["story"]["course_correction"].get("corrected") is True and len(r["story"].get("approaches") or []) < 2]
    assert not bad, f"{len(bad)} corrected session(s) list fewer than two approaches"


def test_the_t020_labels_are_unchanged():
    keep = {r["capture_session_id"]: {"labels": r["labels"],
                                      "course_correction": r["story"]["course_correction"],
                                      "on_track_algorithms": r["story"]["on_track_algorithms"],
                                      "key_facts": r["key_facts"]} for r in _rows()}
    got = hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()
    assert got == T020_PIN, "labels / course_correction / key_facts changed: needs a written reason in T-029"
