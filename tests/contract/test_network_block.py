"""Contract: tests never reach an LLM provider unless marked `llm` (architecture §12).

Tester-owned. Checks the harness in `tests/conftest.py`, which every other test relies on to
keep `tests/` free of real LLM calls.
"""

import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("address", [("api.openai.com", 443), ("api.anthropic.com", 443), ("1.1.1.1", 443)])
def test_unmarked_test_cannot_open_outbound_connection(address):
    with pytest.raises(RuntimeError, match="blocked"):
        socket.create_connection(address, timeout=2)


def test_unmarked_test_cannot_resolve_provider_hosts():
    with pytest.raises(RuntimeError, match="blocked"):
        socket.getaddrinfo("generativelanguage.googleapis.com", 443)


def test_loopback_stays_open():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    t = threading.Thread(target=lambda: server.accept()[0].close(), daemon=True)
    t.start()
    with socket.create_connection(("127.0.0.1", port), timeout=2):
        pass
    t.join(2)
    server.close()


def test_llm_tests_are_deselected_by_default(tmp_path):
    shutil.copy(REPO / "tests" / "conftest.py", tmp_path / "conftest.py")
    (tmp_path / "test_probe.py").write_text(
        "import pytest\n"
        "def test_plain():\n    pass\n"
        "@pytest.mark.llm\ndef test_live():\n    pass\n"
    )
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert "1 passed, 1 deselected" in out.stdout, out.stdout + out.stderr

    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "llm", str(tmp_path)],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert "1 passed, 1 deselected" in out.stdout, out.stdout + out.stderr
