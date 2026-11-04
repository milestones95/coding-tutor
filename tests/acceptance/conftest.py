"""Acceptance-test config (tester-owned).

`live_capture` tests read the human's real capture data under `data/` or need a real browser
action. They are skipped unless selected explicitly:

    uv run pytest tests/acceptance -m live_capture
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_capture: reads real capture data in data/ or needs a real browser action; "
        "skipped unless run with -m live_capture",
    )


def pytest_collection_modifyitems(config, items):
    if "live_capture" in (config.option.markexpr or ""):
        return
    skip = pytest.mark.skip(reason="live_capture: run with -m live_capture")
    for item in items:
        if "live_capture" in item.keywords:
            item.add_marker(skip)
