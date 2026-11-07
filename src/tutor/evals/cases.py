"""Eval cases and the sealed test split (architecture §8.1, §8.2; CLAUDE.md rule 2; D-049).

A `Case` is one line of `evals/data/<suite>/<split>/cases.jsonl`. It points at a session (a real one
in the frozen capture copy, or a human-written synthetic file) and carries `expected`, the human's
label. Labels never leave this package for an inference module: the runner hands field functions
a `Session` only (§4.3 #1).

The test split is sealed: `load_cases` refuses it unless the caller names a milestone the human
approved in `evals/test_approvals.json`. The lock lives here, in the one loader, so no caller can
forget it.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from tutor.capture.loader import CaptureLoader
from tutor.config import REPO_ROOT, Settings
from tutor.models import Session

SUITES = ("failure", "algorithm", "timeline", "agent")
SPLITS = ("dev", "test")
DEFAULT_ROOT = REPO_ROOT / "evals"


class CaseError(Exception):
    """A case file or case that can't be used as written."""


class SplitLockedError(Exception):
    """The sealed test split was requested without an approved milestone (rule 2)."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SessionRef(_Model):
    capture_session_id: str | None = None
    synthetic_path: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "SessionRef":
        if (self.capture_session_id is None) == (self.synthetic_path is None):
            raise ValueError("session needs exactly one of capture_session_id / synthetic_path")
        return self


class Case(_Model):
    case_id: str
    suite: Literal["failure", "algorithm", "timeline", "agent"]
    split: Literal["dev", "test"]
    dataset_version: str
    source: Literal["real", "synthetic"]
    session: SessionRef
    expected: dict
    label_source: Literal["human_written"]
    tags: list[str] = []
    notes: str = ""

    @model_validator(mode="after")
    def _source_matches_session(self) -> "Case":
        if self.source == "real" and self.session.capture_session_id is None:
            raise ValueError("a real case needs session.capture_session_id")
        if self.source == "synthetic" and self.session.synthetic_path is None:
            raise ValueError("a synthetic case needs session.synthetic_path")
        return self


def _check_lock(root: Path, milestone: str | None) -> None:
    approvals = root / "test_approvals.json"
    if milestone is None:
        raise SplitLockedError("the test split is sealed: pass --split test --milestone <id> (rule 2)")
    try:
        approved = json.loads(approvals.read_text()).get("approved", [])
    except FileNotFoundError:
        raise SplitLockedError(f"no {approvals}: the human hasn't approved any test-split run") from None
    if milestone not in approved:
        raise SplitLockedError(f"milestone {milestone!r} isn't approved in {approvals.name}")


def load_cases(suite: str, split: str, *, root: Path | None = None, milestone: str | None = None) -> list[Case]:
    if suite not in SUITES:
        raise ValueError(f"unknown suite {suite!r}; one of {SUITES}")
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; one of {SPLITS}")
    root = (root or DEFAULT_ROOT).resolve()
    path = (root / "data" / suite / split / "cases.jsonl").resolve()
    if path.parent != (root / "data" / suite / split).resolve() or path.parent.name != split:
        raise ValueError(f"{path} isn't the {suite}/{split} cases file")
    if split == "test":
        _check_lock(root, milestone)
    if not path.is_file():
        raise CaseError(f"no cases file at {path}")
    out: list[Case] = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = Case.model_validate(json.loads(line))
        except (json.JSONDecodeError, ValidationError) as e:
            raise CaseError(f"{path.name}:{n}: {e}") from None
        if (case.suite, case.split) != (suite, split):
            raise CaseError(f"{path.name}:{n}: case says {case.suite}/{case.split}, file is {suite}/{split}")
        out.append(case)
    ids = [c.case_id for c in out]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise CaseError(f"{path.name}: duplicate case ids {dupes}")
    return out


def load_case_session(case: Case, *, settings: Settings, root: Path | None = None) -> Session:
    """The `Session` a case points at. Real cases come only from the frozen copy (D-016)."""
    root = (root or DEFAULT_ROOT).resolve()
    if case.session.capture_session_id is not None:
        loader = CaptureLoader(settings.paths.eval_capture_db, mode="immutable", settings=settings)
        try:
            return loader.load_session(case.session.capture_session_id)
        except LookupError as e:
            raise CaseError(f"{case.case_id}: {e}") from None
    assert case.session.synthetic_path is not None
    allowed = (root / "data" / "sessions" / "synthetic").resolve()
    path = (root.parent / case.session.synthetic_path).resolve()
    if path.parent != allowed:
        raise CaseError(f"{case.case_id}: synthetic_path must be a file in {allowed}")
    meta = path.parent / f"{path.stem}.meta.json"
    try:
        verdict = json.loads(meta.read_text()).get("verdict")
    except FileNotFoundError:
        raise CaseError(f"{case.case_id}: no {meta.name}; an unreviewed session can't be used") from None
    if verdict != "accepted":
        raise CaseError(f"{case.case_id}: {meta.name} says {verdict!r}, not 'accepted'")
    try:
        return Session.model_validate_json(path.read_text())
    except (FileNotFoundError, ValidationError) as e:
        raise CaseError(f"{case.case_id}: {e}") from None
