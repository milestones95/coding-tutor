"""Capture DB + verdicts.csv → validated `Session` objects (architecture §4.4, D-011, D-016, D-024).

The capture DB belongs to the ingest server; this module only ever reads it:

- The connection is opened through a SQLite URI with `mode=ro`, so SQLite itself refuses
  writes and refuses to create a missing file. Read-only isn't a promise this code makes, it's
  a property of the connection.
- The caller picks the file and the mode. `ro` is for the live file: it is in WAL mode and
  written concurrently, and `ro` sees rows the server committed but hasn't checkpointed yet.
  `immutable` is for the frozen eval copy: SQLite skips locking and change detection, which
  is only correct for a file nobody writes. So `immutable` on the live path is refused.
- Only four tables are read, by named columns: sessions (id, slug, started_at), snapshots,
  judge_events and problems. The old extension analyzer's output in the same file is never
  selected (the extension-analysis fence, §4.3 #3).

A session is skipped, and logged as `session_excluded`, when the human marked it EXCLUDE in
verdicts.csv (`human_exclude`), or when it has at most one snapshot and no judge events
(`no_activity`: the page was opened and the code never changed).
"""

import csv
import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from tutor.config import Settings
from tutor.logs import log_event, new_run_id
from tutor.models import Problem, RunEvent, Session, Snapshot, SubmitEvent

Mode = Literal["ro", "immutable"]


class CaptureFormatError(Exception):
    """A captured row this project can't read. The message names the session, table and row."""


class VerdictConflict(Exception):
    """verdicts.csv and a captured submit disagree about the same session's verdict."""


@dataclass(frozen=True)
class VerdictRow:
    """One row of verdicts.csv (D-005), the human's backfill for sessions captured before the fix."""

    session_id: str
    verdict: str | None
    tests_passed: int | None
    tests_total: int | None
    exclude: bool


def parse_ts(text: str) -> datetime:
    """Parse a capture timestamp (ISO-8601, `Z` or an offset) to an aware datetime.

    Raises ValueError on anything else, including a timestamp with no zone: capture always
    writes UTC with `Z`, so a zone-less value is a format change, not something to guess about.
    """
    if not isinstance(text, str):
        raise ValueError(f"not a timestamp: {text!r}")
    t = datetime.fromisoformat(text.replace("Z", "+00:00") if text.endswith("Z") else text)
    if t.tzinfo is None:
        raise ValueError(f"timestamp has no timezone: {text!r}")
    return t


def _ts_sort_key(text):
    """Sort key: the parsed time, or the raw text for a bad one (which then raises when parsed)."""
    try:
        return (0, parse_ts(text).timestamp())
    except (ValueError, TypeError):
        return (1, str(text))


def _int_or_none(text: str | None) -> int | None:
    text = (text or "").strip()
    return int(text) if text else None


def read_verdicts(path: Path) -> dict[str, VerdictRow]:
    """verdicts.csv keyed by session id. A missing file means no backfill (D-024)."""
    if not path.is_file():
        return {}
    rows: dict[str, VerdictRow] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for n, r in enumerate(csv.DictReader(f), start=2):  # line 1 is the header
            sid = (r.get("session_id") or "").strip()
            if not sid:
                raise CaptureFormatError(f"{path.name} line {n}: no session_id")
            if sid in rows:
                raise CaptureFormatError(f"{path.name} line {n}: session {sid} is listed twice")
            try:
                rows[sid] = VerdictRow(
                    session_id=sid,
                    verdict=(r.get("verdict") or "").strip() or None,
                    tests_passed=_int_or_none(r.get("tests_passed")),
                    tests_total=_int_or_none(r.get("tests_total")),
                    exclude=(r.get("note") or "").strip().upper().startswith("EXCLUDE"),
                )
            except ValueError as e:
                raise CaptureFormatError(f"{path.name} line {n} (session {sid}): {e}") from None
    return rows


class CaptureLoader:
    """Loads sessions from one capture DB file, opened read-only in the mode the caller gives."""

    def __init__(self, path: Path | str, *, mode: Mode, settings: Settings, run_id: str | None = None):
        if mode not in ("ro", "immutable"):
            raise ValueError(f"mode must be 'ro' or 'immutable', not {mode!r}")
        self.path = Path(path)
        if mode == "immutable" and self.path.resolve() == Path(settings.paths.capture_db).resolve():
            raise ValueError(
                f"immutable=1 refused on the live capture DB {settings.paths.capture_db}: it is written "
                "concurrently and SQLite would miss committed rows. Use mode='ro' (D-016)."
            )
        self.mode = mode
        self.settings = settings
        self.run_id = run_id or new_run_id()
        self._verdicts = read_verdicts(Path(settings.paths.verdicts))
        self._tz = ZoneInfo(settings.time.timezone)
        self._log_path = Path(settings.paths.logs) / "pipeline.jsonl"

    # -- public ---------------------------------------------------------------------------

    def iter_sessions(self, since: datetime | None = None) -> Iterator[Session]:
        """Every real session, ordered by start time; non-attempts are logged and skipped."""
        with self._connect() as con:
            for sid, slug, started in self._session_rows(con):
                if since is not None and started < since:
                    continue
                result = self._build(con, sid, slug, started)
                if isinstance(result, Session):
                    yield result
                else:
                    log_event("session_excluded", run_id=self.run_id, path=self._log_path,
                              session_id=sid, slug=slug, reason=result)

    def load_session(self, session_id: str) -> Session:
        """One session by id. LookupError if it doesn't exist or is excluded as a non-attempt."""
        with self._connect() as con:
            row = con.execute("SELECT id, slug, started_at FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                raise LookupError(f"no session {session_id!r} in {self.path}")
            sid, slug, started = row
            result = self._build(con, sid, slug, self._ts(started, sid, "sessions", sid))
        if not isinstance(result, Session):
            raise LookupError(f"session {session_id!r} is excluded ({result})")
        return result

    # -- internals ------------------------------------------------------------------------

    def _connect(self) -> "_Closing":
        uri = self.path.resolve().as_uri() + ("?mode=ro&immutable=1" if self.mode == "immutable" else "?mode=ro")
        con = sqlite3.connect(uri, uri=True)
        return _Closing(con)

    def _ts(self, text: str, sid: str, table: str, row_id) -> datetime:
        try:
            return parse_ts(text)
        except ValueError as e:
            raise CaptureFormatError(f"session {sid}: {table} row {row_id}: bad timestamp ({e})") from None

    def _session_rows(self, con) -> list[tuple[str, str, datetime]]:
        rows = [(sid, slug, self._ts(started, sid, "sessions", sid))
                for sid, slug, started in con.execute("SELECT id, slug, started_at FROM sessions")]
        return sorted(rows, key=lambda r: (r[2], r[0]))

    def _build(self, con, sid: str, slug: str, started: datetime) -> Session | str:
        """The session, or the reason it is excluded."""
        backfill = self._verdicts.get(sid)
        if backfill and backfill.exclude:
            return "human_exclude"

        snap_rows = con.execute(
            "SELECT id, ts, language, code FROM snapshots WHERE session_id = ?", (sid,)).fetchall()
        judge_rows = con.execute(
            "SELECT id, ts, kind, status, tests_passed, tests_total, error_detail"
            " FROM judge_events WHERE session_id = ?", (sid,)).fetchall()
        if len(snap_rows) <= 1 and not judge_rows:
            return "no_activity"

        try:
            snapshots = [Snapshot(ts=self._ts(ts, sid, "snapshots", rid), code=code, language=lang)
                         for rid, ts, lang, code in sorted(snap_rows, key=lambda r: (_ts_sort_key(r[1]), r[0]))]
            ordered = [self._event(sid, rid, *rest)
                       for rid, *rest in sorted(judge_rows, key=lambda r: (_ts_sort_key(r[1]), r[0]))]
        except ValidationError as e:
            raise CaptureFormatError(f"session {sid}: {_first_error(e)}") from None

        if backfill and backfill.verdict:
            captured = [e for e in ordered if isinstance(e, SubmitEvent)]
            if captured:
                if captured[-1].verdict != backfill.verdict:
                    raise VerdictConflict(
                        f"session {sid}: captured final submit says {captured[-1].verdict!r}, "
                        f"verdicts.csv says {backfill.verdict!r}")
                # they agree: keep the captured submit, which has a real timestamp (D-024)
            else:
                ordered.append(SubmitEvent(ts=None, verdict=backfill.verdict, tests_passed=backfill.tests_passed,
                                           tests_total=backfill.tests_total, error_detail=None,
                                           source="human_resubmit"))

        since = self.settings.capture.submits_reliable_since
        reliable = since is not None and started.astimezone(self._tz).date() >= since
        try:
            return Session(session_id=sid, problem=self._problem(con, sid, slug),
                           snapshots=snapshots, events=ordered,
                           submit_capture_reliable=reliable)
        except ValidationError as e:
            raise CaptureFormatError(f"session {sid}: {_first_error(e)}") from None

    def _event(self, sid, rid, ts, kind, status, passed, total, error_detail) -> RunEvent | SubmitEvent:
        t = self._ts(ts, sid, "judge_events", rid)
        if kind == "run":
            return RunEvent(ts=t, status=status, tests_passed=passed, tests_total=total, error_detail=error_detail)
        if kind == "submit":
            return SubmitEvent(ts=t, verdict=status, tests_passed=passed, tests_total=total,
                               error_detail=error_detail, source="capture_submit")
        raise CaptureFormatError(f"session {sid}: judge_events row {rid}: unknown kind {kind!r}")

    def _problem(self, con, sid: str, slug: str) -> Problem:
        row = con.execute("SELECT slug, title, difficulty, tags, description FROM problems WHERE slug = ?",
                          (slug,)).fetchone()
        if row is None:
            raise CaptureFormatError(f"session {sid}: problems has no row for slug {slug!r}")
        slug, title, difficulty, tags, description = row
        try:
            tag_list = json.loads(tags)
        except (TypeError, json.JSONDecodeError):
            raise CaptureFormatError(f"session {sid}: problems row {slug!r}: tags is not a JSON array") from None
        return Problem(slug=slug, title=title, difficulty=difficulty, tags=tag_list, description=description)


class _Closing:
    """`with` for a sqlite3 connection that closes it (sqlite3's own `with` only commits)."""

    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def __enter__(self) -> sqlite3.Connection:
        return self.con

    def __exit__(self, *exc) -> None:
        self.con.close()


def _first_error(e: ValidationError) -> str:
    err = e.errors(include_url=False)[0]
    return f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
