"""Acceptance tests for T-035's noise-band tool (`evals/report/repeat_band.py`). Tester-owned
(`/test write T-035`, 2026-11-08). Hand-built records whose band is worked out by hand."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _row(case, rep, grades):
    return {"case_id": case, "repeat": rep, "grades": [{"metric": m, "value": v} for m, v in grades]}


REC = {"cases": [
    _row("a", 1, [("type", 1.0), ("expl", 1.0)]), _row("b", 1, [("type", 0.0), ("expl", 0.5)]),
    _row("a", 2, [("type", 1.0), ("expl", 1.0)]), _row("b", 2, [("type", 1.0), ("expl", 1.0)]),
    _row("a", 3, [("type", 1.0)]),                _row("b", 3, []),          # judged nothing; an error row
]}


def test_each_repeat_gets_its_own_mean_over_rows_with_the_metric():
    from evals.report.repeat_band import per_repeat

    assert per_repeat(REC, "type") == [0.5, 1.0, 1.0]
    assert per_repeat(REC, "expl") == [0.75, 1.0], "repeat 3 has no 'expl' grades, so it has no value"


def test_accuracy_reads_the_first_grade_and_counts_an_ungraded_row_as_zero():
    from evals.report.repeat_band import accuracy_per_repeat

    assert accuracy_per_repeat(REC) == [0.5, 1.0, 0.5]


def test_the_band_is_max_minus_min():
    from evals.report.repeat_band import band

    b = band([0.5, 1.0, 1.0])
    assert (b["min"], b["max"], b["band"]) == (0.5, 1.0, 0.5) and b["mean"] == pytest.approx(0.8333, abs=1e-4)
    assert band([0.9, 0.9, 0.9])["band"] == 0.0
    with pytest.raises(ValueError):
        band([])
