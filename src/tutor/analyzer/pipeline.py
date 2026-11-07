"""Part 1's deterministic pipeline: capture → analysis.db (architecture §5.6, §13, D-012, D-037).

Three commands share one shape: load and condense everything in memory first, then write it all
in one `BEGIN … COMMIT`. A session that fails to condense stops the run before the first write,
and any database error during the writes rolls back. So a failed run leaves analysis.db exactly
as it was. A half-written database would read as complete, and Part 2 would answer from it.

Writes are upserts keyed on the primary key: re-running gives the same rows (bar the
loaded_at / built_at stamps), and a session that changed in capture, e.g. a newly captured
submit, is updated in place.

The capture DB is only ever read, through the loader, with `mode=ro` (D-015).
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from tutor.capture.loader import CaptureLoader
from tutor.condense import condense, render
from tutor.config import Settings
from tutor.db.migrate import MIGRATIONS_DIR, current_version, discover, refuse_capture
from tutor.fields.deterministic import attempted_at, status, time_to_finish
from tutor.logs import log_event
from tutor.models import CondensedSession, RunEvent, Session, SubmitEvent


class PipelineError(Exception):
    """The analysis DB can't be used as it is (missing, unmigrated, or a capture path)."""


@dataclass(frozen=True)
class AnalyzeReport:
    stored: int


@dataclass(frozen=True)
class RebuildReport:
    rebuilt: int
    orphaned: list[str]
    not_analyzed: int


def _iso(t: datetime) -> str:
    """ISO-8601 UTC with milliseconds and Z, the way the capture DB writes timestamps."""
    return t.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _now() -> str:
    return _iso(datetime.now(UTC))


def open_analysis_db(settings: Settings) -> sqlite3.Connection:
    """A writable connection to a migrated analysis.db. Never creates the file."""
    path = Path(settings.paths.analysis_db)
    try:
        refuse_capture(path, settings)
    except Exception as e:
        raise PipelineError(str(e)) from None
    if not path.is_file():
        raise PipelineError(f"{path} does not exist; run `tutor migrate` first")
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, isolation_level=None)
    latest = len(discover(MIGRATIONS_DIR))
    have = current_version(con)
    if have < latest:
        con.close()
        raise PipelineError(f"{path} is at migration {have}, latest is {latest}; run `tutor migrate`")
    return con


def since_utc(since: date, settings: Settings) -> datetime:
    """Local midnight of `since` in time.timezone, as a UTC instant."""
    return datetime.combine(since, time(0), tzinfo=ZoneInfo(settings.time.timezone)).astimezone(UTC)


def _condense(session: Session, settings: Settings) -> CondensedSession:
    c = settings.condenser
    return condense(session, interval_s=c.interval_s, error_max_chars=c.error_max_chars, token_budget=c.token_budget)


# ---------------------------------------------------------------- rows


def _problem_row(s: Session) -> tuple:
    p = s.problem
    return (p.slug, p.title, p.difficulty, json.dumps(p.tags))


def _session_row(s: Session, settings: Settings, run_id: str, now: str) -> tuple:
    utc, local = attempted_at(s, settings=settings)
    st = status(s, settings=settings, run_id=run_id)
    runs = sum(isinstance(e, RunEvent) for e in s.events)
    submits = sum(isinstance(e, SubmitEvent) and e.ts is not None for e in s.events)
    return (s.session_id, s.problem.slug, _iso(utc), local.isoformat(), time_to_finish(s), st.status.value,
            st.leetcode_verdict, st.tests_passed, st.tests_total, st.status_source.value, runs, submits, now)


def _timeline_row(c: CondensedSession, now: str) -> tuple:
    text = render(c)
    return (c.session_id, c.condenser_version, c.model_dump_json(), text, c.est_tokens, int(c.truncated), now)


UPSERT_PROBLEM = """INSERT INTO problems (slug, title, difficulty, tags) VALUES (?, ?, ?, ?)
  ON CONFLICT(slug) DO UPDATE SET title = excluded.title, difficulty = excluded.difficulty, tags = excluded.tags"""

UPSERT_SESSION = """INSERT INTO sessions (session_id, slug, attempted_at_utc, attempted_date_local,
    time_to_finish_min, status, leetcode_verdict, tests_passed, tests_total, status_source, run_count,
    submit_count, loaded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  ON CONFLICT(session_id) DO UPDATE SET slug = excluded.slug, attempted_at_utc = excluded.attempted_at_utc,
    attempted_date_local = excluded.attempted_date_local, time_to_finish_min = excluded.time_to_finish_min,
    status = excluded.status, leetcode_verdict = excluded.leetcode_verdict, tests_passed = excluded.tests_passed,
    tests_total = excluded.tests_total, status_source = excluded.status_source, run_count = excluded.run_count,
    submit_count = excluded.submit_count, loaded_at = excluded.loaded_at"""

UPSERT_TIMELINE = """INSERT INTO condensed_timelines (session_id, condenser_version, timeline_json, rendered_text,
    est_tokens, truncated, built_at) VALUES (?, ?, ?, ?, ?, ?, ?)
  ON CONFLICT(session_id) DO UPDATE SET condenser_version = excluded.condenser_version,
    timeline_json = excluded.timeline_json, rendered_text = excluded.rendered_text,
    est_tokens = excluded.est_tokens, truncated = excluded.truncated, built_at = excluded.built_at"""


def _write(con: sqlite3.Connection, statements: list[tuple[str, list[tuple]]]) -> None:
    """Every statement in one transaction: all of it lands, or none of it does."""
    con.execute("BEGIN")
    try:
        for sql, rows in statements:
            con.executemany(sql, rows)
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------- commands


def _loader(settings: Settings, run_id: str) -> CaptureLoader:
    return CaptureLoader(settings.paths.capture_db, mode="ro", settings=settings, run_id=run_id)


def analyze(settings: Settings, *, run_id: str, since: date | None = None) -> AnalyzeReport:
    con = open_analysis_db(settings)
    try:
        log = Path(settings.paths.logs) / "pipeline.jsonl"
        now = _now()
        problems, sessions, timelines = {}, [], []
        start = since_utc(since, settings) if since is not None else None
        for s in _loader(settings, run_id).iter_sessions(since=start):
            log_event("session_loaded", run_id=run_id, path=log, session_id=s.session_id, slug=s.problem.slug)
            c = _condense(s, settings)
            log_event("session_condensed", run_id=run_id, path=log, session_id=s.session_id,
                      est_tokens=c.est_tokens, truncated=c.truncated)
            problems[s.problem.slug] = _problem_row(s)
            sessions.append(_session_row(s, settings, run_id, now))
            timelines.append(_timeline_row(c, now))
        _write(con, [(UPSERT_PROBLEM, list(problems.values())), (UPSERT_SESSION, sessions),
                     (UPSERT_TIMELINE, timelines)])
        return AnalyzeReport(stored=len(sessions))
    finally:
        con.close()


def rebuild_timelines(settings: Settings, *, run_id: str) -> RebuildReport:
    con = open_analysis_db(settings)
    try:
        log = Path(settings.paths.logs) / "pipeline.jsonl"
        now = _now()
        analyzed = {sid for (sid,) in con.execute("SELECT session_id FROM sessions")}
        stored = {sid for (sid,) in con.execute("SELECT session_id FROM condensed_timelines")}
        rows, loaded, not_analyzed = [], set(), 0
        for s in _loader(settings, run_id).iter_sessions():
            loaded.add(s.session_id)
            if s.session_id not in analyzed:
                not_analyzed += 1  # analyze's job: a timeline needs its sessions row first
                continue
            rows.append(_timeline_row(_condense(s, settings), now))
        orphaned = sorted(stored - loaded)
        for sid in orphaned:  # kept, never deleted (D-012)
            log_event("timeline_orphaned", run_id=run_id, path=log, session_id=sid)
        _write(con, [(UPSERT_TIMELINE, rows)])
        return RebuildReport(rebuilt=len(rows), orphaned=orphaned, not_analyzed=not_analyzed)
    finally:
        con.close()


def check(settings: Settings) -> list[tuple[str, str, str | None]]:
    """(session_id, analysis version, timeline version) for every stale analysis row. A missing
    timeline counts as stale: the fields were built from a timeline that's no longer stored."""
    con = open_analysis_db(settings)
    try:
        return list(con.execute(
            "SELECT a.session_id, a.condenser_version, t.condenser_version FROM session_analysis a"
            " LEFT JOIN condensed_timelines t USING (session_id)"
            " WHERE t.condenser_version IS NULL OR t.condenser_version != a.condenser_version"
            " ORDER BY a.session_id"))
    finally:
        con.close()
