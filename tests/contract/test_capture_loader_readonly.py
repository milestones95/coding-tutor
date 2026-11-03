"""Capture DB is input only — D-011, D-016, architecture §4.4. Tester-owned; kept for the life of
the project (`/test write T-004`, 2026-11-03).

The capture DB belongs to the ingest server. This project must never write, migrate or create
it, and must read the live file in a way that sees what the server has committed.
"""

import hashlib
import sqlite3

import pytest

from _capture_fixture import build
from tutor.config import load_settings


def _settings(tmp_path, live):
    return load_settings(env={"TUTOR__PATHS__CAPTURE_DB": str(live),
                              "TUTOR__PATHS__VERDICTS": str(tmp_path / "none.csv"),
                              "TUTOR__PATHS__LOGS": str(tmp_path / "logs")},
                         dotenv_path=tmp_path / "none.env")


def _db(tmp_path, name="cap.db"):
    sid = "s-1"
    return build(tmp_path / name, sessions=[{"id": sid, "started_at": "2026-11-01T10:00:00.000Z"}],
                 snapshots=[{"session_id": sid, "ts": f"2026-11-01T10:00:0{i}.000Z", "code": f"{i}"} for i in range(3)])


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.parametrize("mode", ["ro", "immutable"])
def test_loading_never_changes_the_capture_file(tmp_path, mode):
    from tutor.capture.loader import CaptureLoader

    db = _db(tmp_path)
    live = db if mode == "ro" else tmp_path / "elsewhere.db"
    before = _sha(db)
    ld = CaptureLoader(db, mode=mode, settings=_settings(tmp_path, live))
    list(ld.iter_sessions())
    ld.load_session("s-1")
    assert _sha(db) == before


@pytest.mark.parametrize("mode", ["ro", "immutable"])
def test_a_missing_capture_file_is_an_error_and_is_not_created(tmp_path, mode):
    from tutor.capture.loader import CaptureLoader

    missing = tmp_path / "nope.db"
    with pytest.raises(Exception):
        list(CaptureLoader(missing, mode=mode, settings=_settings(tmp_path, tmp_path / "live.db")).iter_sessions())
    assert not missing.exists(), "opening the capture DB created a file — it was not opened read-only"


def test_ro_mode_sees_rows_the_ingest_server_committed_to_its_wal(tmp_path):
    """The live file is WAL and written concurrently: mode=ro must see committed rows still in
    the -wal file, which is exactly what immutable=1 would miss (why D-016 refuses it)."""
    from tutor.capture.loader import CaptureLoader

    db = _db(tmp_path)
    writer = sqlite3.connect(db)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("INSERT INTO sessions (id, slug, started_at, last_activity_at, end_reason, analysis_status)"
                   " VALUES ('s-2', 'probe-problem', '2026-11-01T11:00:00.000Z', '2026-11-01T11:00:00.000Z', 'ended', 'open')")
    writer.executemany("INSERT INTO snapshots (session_id, ts, language, code) VALUES ('s-2', ?, 'python3', ?)",
                       [(f"2026-11-01T11:00:0{i}.000Z", f"w{i}") for i in range(2)])
    writer.commit()  # committed, not checkpointed: the rows live only in cap.db-wal
    try:
        got = [s.session_id for s in CaptureLoader(db, mode="ro", settings=_settings(tmp_path, db)).iter_sessions()]
    finally:
        writer.close()
    assert got == ["s-1", "s-2"]

