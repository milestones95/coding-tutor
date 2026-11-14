"""Contract: one algorithm label list (D-070). Tester-owned (`/test write T-042`, 2026-11-14).

The list lives in several places because each layer needs it in its own form. If they drift, the
eval grades the model against a label it can't answer (a checker-only label is a guaranteed miss),
or the database refuses a label the model may give. Every copy must hold the same set:

- `tutor.models.AlgorithmLabel`             what the model may answer
- the pinned algorithm prompt's `- label:`  what the model is offered
- `algorithm_labels` after migrating       what analysis.db accepts
- `check_specs.ALGORITHMS`                 what a spec may be labelled
- `checks.ALGO_WORDS`                      the giveaway words per label
- `keyword_baseline.CUES`                  the baseline's labels
"""

import re
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def _enum() -> set[str]:
    from tutor.models import AlgorithmLabel

    return {a.value for a in AlgorithmLabel}


def test_the_pinned_prompt_offers_exactly_the_enum():
    from tutor.config import load_settings

    pin = load_settings().prompts["algorithm"]
    text = (REPO / "prompts" / "algorithm" / f"{pin}.md").read_text()
    offered = set(re.findall(r"(?m)^- ([a-z_]+):", text))
    assert offered == _enum()


def test_the_migrated_database_accepts_exactly_the_enum(tmp_path):
    from tutor.config import load_settings
    from tutor.db.migrate import migrate

    settings = load_settings(env={"TUTOR__PATHS__CAPTURE_DB": str(tmp_path / "c.db"),
                                  "TUTOR__PATHS__EVAL_CAPTURE_DB": str(tmp_path / "f.db"),
                                  "TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")
    path = tmp_path / "analysis.db"
    migrate(path, settings=settings)
    rows = {lab for (lab,) in sqlite3.connect(path).execute("SELECT label FROM algorithm_labels")}
    assert rows == _enum()


def test_the_spec_checker_allows_exactly_the_enum():
    sys.path.insert(0, str(REPO / "evals" / "generate"))
    from check_specs import ALGORITHMS

    assert set(ALGORITHMS) == _enum()


def test_the_session_checker_and_keyword_baseline_cover_exactly_the_enum():
    from evals.generate.checks import ALGO_WORDS
    from evals.graders.keyword_baseline import CUES

    assert set(ALGO_WORDS) == _enum()
    assert set(CUES) == _enum()
