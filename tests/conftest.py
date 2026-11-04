"""Shared test harness — tester-owned (rule 11; `/test write T-003`, 2026-11-02).

- Tests marked `llm` may call a real provider. They are deselected unless selected:
      uv run pytest -m llm
- Every other test runs with outbound network blocked. Loopback (127.0.0.1, ::1,
  localhost) stays open, so tests can talk to a local server they started themselves.
  Child processes are not affected; this guards in-process provider calls.
"""

import ipaddress
import socket

import pytest


class NetworkBlocked(RuntimeError):
    """Raised when a test without the `llm` marker opens a non-loopback connection."""


def pytest_configure(config):
    config.addinivalue_line("markers", "llm: calls a real LLM provider; deselected unless run with -m llm")
    if not config.option.markexpr:
        config.option.markexpr = "not llm"


def _is_loopback(host) -> bool:
    if host in (None, "", "localhost"):
        return True
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def _block_network(request, monkeypatch):
    if request.node.get_closest_marker("llm"):
        yield
        return

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def _host(address):
        return address[0] if isinstance(address, tuple) else None  # AF_UNIX paths are local

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_loopback(_host(address)):
            raise NetworkBlocked(f"network blocked in tests without @pytest.mark.llm: {address!r}")
        return real_connect(self, address)

    def connect_ex(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_loopback(_host(address)):
            raise NetworkBlocked(f"network blocked in tests without @pytest.mark.llm: {address!r}")
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if not _is_loopback(host if not isinstance(host, bytes) else host.decode()):
            raise NetworkBlocked(f"DNS lookup blocked in tests without @pytest.mark.llm: {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    yield
