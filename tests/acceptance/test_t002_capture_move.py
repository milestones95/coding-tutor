"""Acceptance tests for T-002: move capture (extension + ingest server) into this repo.

Tester-owned (`/test write T-002`, 2026-11-02). One or more tests per Done-when condition in
`docs/tracker.md`. Done-when 3 (Chrome loads the unpacked extension from this repo; the old
copy is removed) needs a human in a browser and is confirmed in the task log, not here.

Conventions agreed with the human for this task:
- The ingest server starts with `npm --prefix ux-extension start`.
- Seeding writes `data/capture.seed.json`:
  {"source_path": str, "source_sha256": str, "seeded_at": ISO-8601 UTC,
   "row_counts": {table: int, ...}}
  `source_sha256` is the sha256 of the source DB file's bytes followed by its `-wal` file's
  bytes when one exists, taken after the old server was stopped.

Tests marked `live_capture` read the human's real data and are skipped unless run with
`-m live_capture`. Everything else uses temp files and a spare port, never `data/` or 7777.
"""

import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
UX = REPO / "ux-extension"
SERVER_SRC = UX / "server" / "src"
FIXTURES = REPO / "evals" / "fixtures" / "capture"

LIVE_DB = REPO / "data" / "capture.db"
SEED_RECORD = REPO / "data" / "capture.seed.json"
OLD_DB_SUFFIX = "leetcode-analyzer/data/leetcode.db"
CAPTURE_TABLES = ("problems", "sessions", "snapshots", "judge_events", "attempts", "attempt_gaps")
APPEND_ONLY = ("snapshots", "judge_events", "attempts", "attempt_gaps")  # rows never updated

ALLOWED_SERVER_FILES = {
    "ingest.ts", "db.ts", "judge.ts", "sessions.ts", "taxonomy.ts", "config.ts",
    "seed-problems.ts", "diff.ts",
}
REQUIRED_SERVER_FILES = {"ingest.ts", "db.ts", "judge.ts", "sessions.ts", "config.ts"}
REQUIRED_EXTENSION_FILES = {"manifest.json", "page-hook.js", "relay.js", "background.js"}
ALLOWED_UX_TOP = {
    "extension", "server", "package.json", "package-lock.json", "tsconfig.json",
    "README.md", ".nvmrc", ".gitignore", "node_modules",
}

PROBE_PORT = 7791  # never 7777: the human's real server may be running there


def _clean_env(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "PORT" and not k.startswith("LCA_")}
    env.update(extra)
    return env


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


# ---------------------------------------------------------------- Done-when 1


def test_dw1_ux_extension_holds_only_capture_code():
    assert UX.is_dir(), "ux-extension/ is missing"
    extra_top = sorted(p.name for p in UX.iterdir() if p.name not in ALLOWED_UX_TOP)
    assert not extra_top, f"ux-extension/ holds more than capture (D-015): {extra_top}"
    for name in ("package.json", "package-lock.json", "tsconfig.json"):
        assert (UX / name).is_file(), f"ux-extension/{name} is missing"

    server_files = {str(p.relative_to(SERVER_SRC)) for p in SERVER_SRC.rglob("*") if p.is_file()}
    assert server_files <= ALLOWED_SERVER_FILES, f"not capture code (D-015): {sorted(server_files - ALLOWED_SERVER_FILES)}"
    assert REQUIRED_SERVER_FILES <= server_files, f"capture files missing: {sorted(REQUIRED_SERVER_FILES - server_files)}"

    ext_files = {p.name for p in (UX / "extension").iterdir()}
    assert REQUIRED_EXTENSION_FILES <= ext_files, f"extension files missing: {sorted(REQUIRED_EXTENSION_FILES - ext_files)}"


def test_dw1_old_capture_db_location_is_unused():
    stale = sorted(str(p.relative_to(REPO)) for p in (UX / "data").glob("*.db")) if (UX / "data").exists() else []
    assert not stale, f"capture DB must live at data/capture.db, not under ux-extension/: {stale}"


@pytest.fixture
def probe_server(tmp_path):
    """The real ingest server, started the documented way, on a spare port and a temp DB."""
    assert (UX / "node_modules").is_dir(), "run `npm --prefix ux-extension install` first"
    db = tmp_path / "probe.db"
    log = (tmp_path / "server.log").open("w")
    proc = subprocess.Popen(
        ["npm", "--prefix", str(UX), "start"],
        cwd=REPO,
        env=_clean_env(PORT=str(PROBE_PORT), LCA_DB=str(db)),
        stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    base = f"http://127.0.0.1:{PROBE_PORT}"
    try:
        deadline = time.time() + 30
        while True:
            try:
                with urllib.request.urlopen(f"{base}/health", timeout=1) as r:
                    if r.status == 200:
                        break
            except (urllib.error.URLError, ConnectionError, OSError):
                pass
            if proc.poll() is not None or time.time() > deadline:
                log.flush()
                pytest.fail(f"ingest server did not come up:\n{(tmp_path / 'server.log').read_text()[-2000:]}")
            time.sleep(0.3)
        yield base, db
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        proc.wait(timeout=10)
        log.close()


def _post(base: str, event: dict) -> dict:
    req = urllib.request.Request(
        f"{base}/events", data=json.dumps(event).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


def test_dw1_session_end_stores_events_and_runs_no_analysis(probe_server):
    base, db = probe_server
    slug = "t002-probe"
    run_response = json.loads((FIXTURES / "run_check_success.json").read_text())
    events = [
        {"type": "problem_view", "slug": slug, "ts": "2026-01-05T15:00:00.000Z",
         "problem": {"title": "T002 Probe", "difficulty": "Easy", "tags": ["array"]}},
        {"type": "snapshot", "slug": slug, "ts": "2026-01-05T15:00:10.000Z", "language": "python3",
         "code": "class Solution:\n    pass\n"},
        {"type": "snapshot", "slug": slug, "ts": "2026-01-05T15:00:20.000Z", "language": "python3",
         "code": "class Solution:\n    def f(self):\n        return 1\n"},
        {"type": "judge", "slug": slug, "ts": "2026-01-05T15:00:30.000Z",
         "url": f"https://leetcode.com/submissions/detail/{run_response['submission_id']}/check/",
         "data": run_response},
        {"type": "session_end", "slug": slug, "ts": "2026-01-05T15:00:40.000Z", "reason": "ended"},
    ]
    for e in events:
        assert _post(base, e).get("ok") is True
    time.sleep(1.0)  # an analyzer, if one were still wired in, would have started by now

    con = _ro(db)
    sessions = con.execute("SELECT id, ended_at, end_reason, analysis_status FROM sessions WHERE slug = ?", (slug,)).fetchall()
    assert len(sessions) == 1, sessions
    sid, ended_at, end_reason, analysis_status = sessions[0]
    assert ended_at is not None and end_reason == "ended"
    assert analysis_status in ("open", "skipped"), f"an analysis was queued or run on session end: {analysis_status}"

    assert con.execute("SELECT COUNT(*) FROM snapshots WHERE session_id = ?", (sid,)).fetchone()[0] == 2
    judges = con.execute("SELECT kind, submission_id FROM judge_events WHERE session_id = ?", (sid,)).fetchall()
    assert judges == [("run", run_response["submission_id"])]
    con.close()


def test_dw1_dashboard_route_is_gone(probe_server):
    base, _ = probe_server
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(f"{base}/dashboard", timeout=5)
    assert err.value.code == 404


# ---------------------------------------------------------------- Done-when 2


def test_dw2_readme_documents_install_and_start():
    readme = UX / "README.md"
    assert readme.is_file(), "ux-extension/README.md is missing"
    text = readme.read_text()
    assert "npm --prefix ux-extension install" in text or "npm install" in text, "README lacks the install command"
    assert "npm --prefix ux-extension start" in text or "npm start" in text, "README lacks the start command"
    assert "ux-extension/extension" in text, "README must say which folder Chrome loads as the unpacked extension"


def test_dw2_server_defaults_to_port_7777_and_repo_capture_db(tmp_path):
    assert (UX / "node_modules").is_dir(), "run `npm --prefix ux-extension install` first"
    probe = tmp_path / "probe_config.mts"
    probe.write_text(
        f'import {{ config }} from {json.dumps(str(SERVER_SRC / "config.ts"))};\n'
        "console.log(JSON.stringify({ port: config.port, dbPath: config.dbPath }));\n"
    )
    out = subprocess.run(
        ["npx", "--no-install", "tsx", str(probe)], cwd=UX, env=_clean_env(),
        capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    cfg = json.loads(out.stdout.strip().splitlines()[-1])
    assert cfg["port"] == 7777
    assert Path(cfg["dbPath"]).resolve() == LIVE_DB.resolve()


# ---------------------------------------------------------------- Done-when 4 (real data)


def _seed() -> dict:
    assert SEED_RECORD.is_file(), "data/capture.seed.json is missing — the seeding step must write it"
    seed = json.loads(SEED_RECORD.read_text())
    assert {"source_path", "source_sha256", "seeded_at", "row_counts"} <= seed.keys(), seed.keys()
    return seed


def _file_sha256(db: Path) -> str:
    h = hashlib.sha256(db.read_bytes())
    wal = db.with_name(db.name + "-wal")
    if wal.exists():
        h.update(wal.read_bytes())
    return h.hexdigest()


@pytest.mark.live_capture
def test_dw4_old_db_is_untouched_since_seeding():
    seed = _seed()
    src = Path(seed["source_path"])
    assert str(src).endswith(OLD_DB_SUFFIX), f"seeded from an unexpected file: {src}"
    assert src.is_file(), f"the old capture DB is gone: {src} (it must be kept as a backup)"
    assert _file_sha256(src) == seed["source_sha256"], "the old capture DB changed after seeding"


@pytest.mark.live_capture
def test_dw4_seeded_row_counts_match_source():
    seed = _seed()
    src = _ro(Path(seed["source_path"]))
    for t in CAPTURE_TABLES:
        n = src.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        assert seed["row_counts"].get(t) == n, f"{t}: seed record says {seed['row_counts'].get(t)}, source has {n}"
    src.close()


@pytest.mark.live_capture
def test_dw4_every_source_row_is_in_the_live_db():
    """Live data keeps growing after the move, so the live DB must be a superset of the source."""
    seed = _seed()
    assert LIVE_DB.is_file(), "data/capture.db is missing"
    src, dst = _ro(Path(seed["source_path"])), _ro(LIVE_DB)
    for t in APPEND_ONLY:
        missing = set(src.execute(f"SELECT * FROM {t}")) - set(dst.execute(f"SELECT * FROM {t}"))
        assert not missing, f"{t}: {len(missing)} source rows missing or changed in data/capture.db"
    for t, key in (("sessions", "id, slug, started_at"), ("problems", "slug")):
        missing = set(src.execute(f"SELECT {key} FROM {t}")) - set(dst.execute(f"SELECT {key} FROM {t}"))
        assert not missing, f"{t}: {len(missing)} source rows missing in data/capture.db"
    src.close(), dst.close()


def test_dw4_seed_count_query_is_saved():
    q = REPO / "scripts" / "discovery" / "16_capture_seed_counts.sql"
    assert q.is_file(), "save the row-count query as scripts/discovery/16_capture_seed_counts.sql"
    text = q.read_text()
    assert "COUNT" in text.upper() and all(t in text for t in CAPTURE_TABLES)


# ---------------------------------------------------------------- Done-when 5 (real browser)


@pytest.mark.live_capture
def test_dw5_a_real_run_event_arrived_after_the_move():
    seed = _seed()
    seeded_at = datetime.fromisoformat(seed["seeded_at"].replace("Z", "+00:00"))
    con = _ro(LIVE_DB)
    rows = con.execute("SELECT ts FROM judge_events WHERE kind = 'run'").fetchall()
    con.close()
    after = [ts for (ts,) in rows if datetime.fromisoformat(ts.replace("Z", "+00:00")) > seeded_at]
    assert after, "no Run event in data/capture.db after seeding — click Run on a LeetCode problem"


# ---------------------------------------------------------------- Done-when 6


def _ignored(path: str) -> bool:
    return subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=REPO).returncode == 0


@pytest.mark.parametrize("path", [
    "data/capture.db", "data/capture.seed.json", "logs/llm_calls.jsonl",
    "ux-extension/node_modules/tsx/package.json", ".env",
])
def test_dw6_gitignore_ignores(path):
    assert _ignored(path), f"{path} must be gitignored"


@pytest.mark.parametrize("path", [
    "docs/data/session-format.md", "ux-extension/package-lock.json",
    "ux-extension/server/src/ingest.ts", "evals/fixtures/capture/run_check_success.json",
])
def test_dw6_gitignore_keeps(path):
    assert not _ignored(path), f"{path} must NOT be gitignored"


# ---------------------------------------------------------------- Done-when 7


def test_dw7_node_is_pinned():
    nvmrc = UX / ".nvmrc"
    assert nvmrc.is_file() and nvmrc.read_text().strip() == "20.19.5"
    pkg = json.loads((UX / "package.json").read_text())
    assert pkg.get("engines", {}).get("node") == ">=20.19.5 <21"


def test_dw2_start_script_exists():
    pkg = json.loads((UX / "package.json").read_text()) if (UX / "package.json").is_file() else {}
    assert "start" in pkg.get("scripts", {}), "package.json needs a `start` script (`npm --prefix ux-extension start`)"
