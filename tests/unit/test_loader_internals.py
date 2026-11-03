"""Builder unit tests for capture/loader.py internals (T-004)."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from _capture_fixture import build, write_verdicts
from tutor.capture.loader import CaptureFormatError, CaptureLoader, parse_ts, read_verdicts
from tutor.config import load_settings


@pytest.mark.parametrize("text,expected", [
    ("2026-11-01T10:00:00.122Z", datetime(2026, 11, 1, 10, 0, 0, 122000, tzinfo=UTC)),
    ("2026-11-01T10:00:00+00:00", datetime(2026, 11, 1, 10, tzinfo=UTC)),
    ("2026-11-01T05:00:00-05:00", datetime(2026, 11, 1, 10, tzinfo=UTC)),
])
def test_parse_ts_accepts_z_and_offsets(text, expected):
    assert parse_ts(text) == expected


@pytest.mark.parametrize("text", ["2026-11-01T10:00:00", "yesterday", "", None])
def test_parse_ts_rejects_zoneless_and_junk(text):
    with pytest.raises(ValueError):
        parse_ts(text)


def test_read_verdicts_blank_counts_and_exclude(tmp_path):
    p = write_verdicts(tmp_path / "v.csv", [
        {"session_id": "a", "verdict": "Accepted", "passed": 5, "total": 5},
        {"session_id": "b", "note": "EXCLUDE: page opened only"},
        {"session_id": "c", "verdict": "Wrong Answer", "note": "verdict type confirmed"},
    ])
    rows = read_verdicts(p)
    assert (rows["a"].verdict, rows["a"].tests_passed, rows["a"].exclude) == ("Accepted", 5, False)
    assert (rows["b"].verdict, rows["b"].tests_total, rows["b"].exclude) == (None, None, True)
    assert rows["c"].exclude is False and rows["c"].tests_passed is None


def test_read_verdicts_rejects_a_session_listed_twice(tmp_path):
    p = write_verdicts(tmp_path / "v.csv", [{"session_id": "a", "verdict": "Accepted"},
                                            {"session_id": "a", "verdict": "Wrong Answer"}])
    with pytest.raises(CaptureFormatError, match="twice"):
        read_verdicts(p)


def _loader(tmp_path, db):
    s = load_settings(env={"TUTOR__PATHS__CAPTURE_DB": str(tmp_path / "live.db"),
                           "TUTOR__PATHS__VERDICTS": str(tmp_path / "none.csv"),
                           "TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")
    return CaptureLoader(db, mode="immutable", settings=s)


def _two_snaps(sid):
    return [{"session_id": sid, "ts": f"2026-11-01T10:00:0{i}.000Z", "code": str(i)} for i in range(2)]


def test_a_session_whose_problem_is_missing_names_the_session(tmp_path):
    db = build(tmp_path / "c.db", sessions=[{"id": "s", "slug": "ghost", "started_at": "2026-11-01T10:00:00.000Z"}],
               snapshots=_two_snaps("s"))
    with pytest.raises(CaptureFormatError, match="s.*ghost"):
        list(_loader(tmp_path, db).iter_sessions())


def test_an_unknown_judge_kind_is_a_format_error(tmp_path):
    db = build(tmp_path / "c.db", sessions=[{"id": "s", "started_at": "2026-11-01T10:00:00.000Z"}],
               snapshots=_two_snaps("s"),
               judge_events=[{"id": 9, "session_id": "s", "ts": "2026-11-01T10:01:00.000Z", "kind": "debug",
                              "status": "x", "submission_id": "q"}])
    with pytest.raises(CaptureFormatError, match="row 9"):
        list(_loader(tmp_path, db).iter_sessions())


def test_a_null_snapshot_language_is_a_format_error(tmp_path):
    snaps = _two_snaps("s")
    snaps[1]["language"] = None
    db = build(tmp_path / "c.db", sessions=[{"id": "s", "started_at": "2026-11-01T10:00:00.000Z"}], snapshots=snaps)
    with pytest.raises(CaptureFormatError, match="session s"):
        list(_loader(tmp_path, db).iter_sessions())


def test_offset_timestamps_are_normalised_to_utc(tmp_path):
    t = datetime(2026, 11, 1, 5, tzinfo=timezone(timedelta(hours=-5)))
    snaps = [{"session_id": "s", "ts": (t + timedelta(seconds=i)).isoformat(), "code": str(i)} for i in range(2)]
    db = build(tmp_path / "c.db", sessions=[{"id": "s", "started_at": t.isoformat()}], snapshots=snaps)
    [s] = list(_loader(tmp_path, db).iter_sessions())
    assert s.snapshots[0].ts.tzinfo == UTC and s.snapshots[0].ts.hour == 10
