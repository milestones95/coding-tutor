"""Acceptance test for T-012: the M1 checkpoint on real sessions (eval-plan condensing tests).

Tester-owned (`/test write T-012`, 2026-11-03). Reads the frozen copy (data/reference/capture.db,
opened immutable), so it is `live_capture`:

    uv run pytest -m live_capture tests/acceptance/test_t012_m1_checkpoint.py

Done-when 2: all 8 frozen sessions condense with the configured settings; every run and submit is
in the timeline; each fits the token budget untruncated; the stored JSON re-renders identically.
Done-when 1 (every gate green) is checked at `/test run`; Done-when 3 (the human reads two real
timelines) is a confirmation in the task log, not a test.
"""

import pytest

from tutor.config import REPO_ROOT

FROZEN = REPO_ROOT / "data" / "reference" / "capture.db"
N_FROZEN = 8  # data/labels/verdicts.csv (D-005); test_t004 pins the same ids


@pytest.fixture(scope="module")
def condensed():
    from tutor.capture.loader import CaptureLoader
    from tutor.condense import condense
    from tutor.config import load_settings

    if not FROZEN.exists():
        pytest.skip("needs the frozen copy at data/reference/capture.db")
    s = load_settings()
    c = s.condenser
    sessions = list(CaptureLoader(FROZEN, mode="immutable", settings=s, run_id="t012-checkpoint").iter_sessions())
    return s, [(x, condense(x, interval_s=c.interval_s, error_max_chars=c.error_max_chars,
                            token_budget=c.token_budget)) for x in sessions]


@pytest.mark.live_capture
def test_dw2_all_frozen_sessions_condense(condensed):
    _, pairs = condensed
    assert len(pairs) == N_FROZEN


@pytest.mark.live_capture
def test_dw2_every_run_and_submit_is_in_the_timeline(condensed):
    _, pairs = condensed
    for s, c in pairs:
        runs = [e for e in s.events if e.kind == "run"]
        subs = [e for e in s.events if e.kind == "submit"]
        assert [m.run for m in c.moments if m.kind == "run"] == runs, s.session_id
        assert [(m.submit.verdict, m.submit.source) for m in c.moments if m.kind == "submit"] == \
            [(e.verdict, e.source) for e in subs], s.session_id


@pytest.mark.live_capture
def test_dw2_each_fits_the_budget_untruncated(condensed):
    settings, pairs = condensed
    for s, c in pairs:
        assert c.est_tokens <= settings.condenser.token_budget, s.session_id
        assert not c.truncated, f"{s.session_id}: real sessions should fit without dropping code"


@pytest.mark.live_capture
def test_dw2_stored_json_rerenders_identically(condensed):
    from tutor.condense import render
    from tutor.models import CondensedSession

    _, pairs = condensed
    for s, c in pairs:
        assert render(CondensedSession.model_validate_json(c.model_dump_json())) == render(c), s.session_id
