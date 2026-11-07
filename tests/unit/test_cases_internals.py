"""Builder unit tests for tutor.evals.cases internals (T-016)."""

import json

import pytest
from pydantic import ValidationError

from tutor.evals.cases import SessionRef, SplitLockedError, _check_lock


def test_session_ref_needs_exactly_one_source():
    assert SessionRef(capture_session_id="a").synthetic_path is None
    for kw in ({}, {"capture_session_id": "a", "synthetic_path": "b"}):
        with pytest.raises(ValidationError):
            SessionRef(**kw)


def test_lock_messages_say_what_to_do(tmp_path):
    with pytest.raises(SplitLockedError, match="--milestone"):
        _check_lock(tmp_path, None)
    (tmp_path / "test_approvals.json").write_text(json.dumps({"approved": []}))
    with pytest.raises(SplitLockedError, match="M7"):
        _check_lock(tmp_path, "M7")
