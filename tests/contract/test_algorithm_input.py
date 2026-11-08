"""Contract: what the algorithm field may show the model (T-024; eval plan "LLM reads the final code";
architecture §6.3; rule 1). Tester-owned (2026-11-07; interfaces D-054).

The input is the final code plus the problem's title, difficulty and tags (tags are hints, §6.3).
It never includes the verdict, test counts, run results or error text, and never the code from
earlier snapshots. Each of those carries a unique sentinel here; none may reach the adapter.
"""

import json
from datetime import UTC, datetime, timedelta

from _llm_fake import FakeAdapter

T0 = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
FINAL = "class Solution:\n    def f(self, nums):\n        seen = {}\n        return seen\n"
SENTINELS = ["VERDICT-SENTINEL-a1", "RUNSTATUS-SENTINEL-b2", "RUNERR-SENTINEL-c3", "SUBERR-SENTINEL-d4",
             "EARLYCODE-SENTINEL-e5", "7777", "8888", "6666", "5555"]


def _session():
    from tutor.models import Problem, RunEvent, Session, Snapshot, SubmitEvent

    return Session(
        session_id="contract-algo-1",
        problem=Problem(slug="probe", title="Probe Problem", difficulty="Medium",
                        tags=["array", "hash-table"], description=None),
        snapshots=[Snapshot(ts=T0, code="# EARLYCODE-SENTINEL-e5\n", language="python3"),
                   Snapshot(ts=T0 + timedelta(minutes=5), code=FINAL, language="python3")],
        events=[RunEvent(ts=T0 + timedelta(minutes=3), status="RUNSTATUS-SENTINEL-b2", tests_passed=6666,
                         tests_total=5555, error_detail="RUNERR-SENTINEL-c3"),
                SubmitEvent(ts=T0 + timedelta(minutes=6), verdict="VERDICT-SENTINEL-a1", tests_passed=7777,
                            tests_total=8888, error_detail="SUBERR-SENTINEL-d4", source="capture_submit")],
        submit_capture_reliable=True,
    )


def test_no_verdict_run_result_or_earlier_code_reaches_the_model(tmp_path):
    from tutor.config import load_settings
    from tutor.fields.algorithm import algorithm
    from tutor.llm import LLMClient

    settings = load_settings(env={"TUTOR__PATHS__LOGS": str(tmp_path / "logs")}, dotenv_path=tmp_path / "none.env")
    fake = FakeAdapter([{"algorithms": ["hash_map"]}])
    algorithm(_session(), client=LLMClient(settings, adapters={"openai": fake}), settings=settings, run_id="r-contract")
    sent = json.dumps([m.model_dump() for m in fake.calls[0]["messages"]])
    assert FINAL.strip().splitlines()[-1].strip() in sent, "the final code is the input"
    leaked = [s for s in SENTINELS if s in sent]
    assert not leaked, f"the algorithm prompt must not see {leaked}"
