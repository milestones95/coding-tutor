"""Contract: what the timeline field may show the model (T-031; architecture §4.3, §6.3; rules 1, 3).
Tester-owned (`/test write T-031`, 2026-11-08; interfaces D-060). Kept for the project's life.

The input is the rendered condensed timeline (verdict, runs and errors included: they are data).
The human's labels in a case's `expected` (approaches, course correction, final approach, key
facts) and its notes never reach the model. Each carries a unique sentinel here.
"""

import json
import shutil
from pathlib import Path

from _llm_fake import FakeAdapter

REPO = Path(__file__).resolve().parents[2]
SYN = REPO / "evals" / "data" / "sessions" / "synthetic"
SUMMARY = "You tried one idea. It was accepted. Nothing else happened."


def _case(n, sid):
    return {"case_id": f"timeline-dev-{n:03d}", "suite": "timeline", "split": "dev", "dataset_version": "dev-v1",
            "source": "synthetic", "session": {"synthetic_path": f"evals/data/sessions/synthetic/{sid}.json"},
            "expected": {"checklist": {"approaches": [f"APPROACH-SENTINEL-{n}"],
                                       "course_correction": {"first_approach_on_track": False, "corrected": True,
                                                             "at_min": 4242.5},
                                       "final_approach": f"FINAL-SENTINEL-{n}", "outcome": f"OUTCOME-SENTINEL-{n}"},
                         "key_facts": [f"KEYFACT-SENTINEL-{n}"]},
            "label_source": "human_written", "tags": ["TAG-SENTINEL"], "notes": "NOTES-SENTINEL"}


def test_no_label_or_case_text_reaches_the_timeline_model(tmp_path):
    from tutor.config import load_settings
    from tutor.evals.runner import predictor_named, run
    from tutor.llm import LLMClient

    syn = tmp_path / "evals" / "data" / "sessions" / "synthetic"
    syn.mkdir(parents=True)
    for sid in ("syn-004", "syn-009"):
        for ext in (".json", ".meta.json"):
            shutil.copy(SYN / f"{sid}{ext}", syn / f"{sid}{ext}")
    f = tmp_path / "evals" / "data" / "timeline" / "dev" / "cases.jsonl"
    f.parent.mkdir(parents=True)
    f.write_text("".join(json.dumps(_case(n, sid)) + "\n" for n, sid in ((1, "syn-004"), (2, "syn-009"))))

    settings = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")
    fake = FakeAdapter([{"summary": SUMMARY}, {"summary": SUMMARY}])
    client = LLMClient(settings, adapters={"openai": fake}, sleep=lambda s: None)
    run("timeline", "dev", predictor=predictor_named("timeline", settings=settings, client=client),
        settings=settings, root=tmp_path / "evals", results_dir=tmp_path / "results")
    sent = json.dumps([[m.model_dump() for m in c["messages"]] for c in fake.calls])
    leaked = [s for s in ("APPROACH-SENTINEL", "FINAL-SENTINEL", "OUTCOME-SENTINEL", "KEYFACT-SENTINEL",
                          "NOTES-SENTINEL", "TAG-SENTINEL", "4242.5", "label_source", "first_approach_on_track")
              if s in sent]
    assert len(fake.calls) == 2
    assert not leaked, f"rule 1: case labels reached the timeline model: {leaked}"
