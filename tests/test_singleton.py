"""Tests for _get_transport singleton — thread safety, partial init recovery."""
import threading
from unittest.mock import patch, MagicMock

import claude_code_orchestrate.client as client_mod
from claude_code_orchestrate.mcp_transport import MCPTransport, ClaudeCodeError


def setup_function():
    client_mod._transport = None


def test_partial_init_recovery():
    """If start() fails, next call must retry — not return the broken transport."""
    call_count = [0]

    class FlakyTransport:
        def __init__(self):
            self._proc = None
            self._request_id = 0
            self._tools = []
            self._lock = threading.Lock()

        def start(self):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ClaudeCodeError("transport", "connection refused")

        def stop(self):
            pass

    with patch("claude_code_orchestrate.client.MCPTransport", FlakyTransport):
        # First call fails
        try:
            client_mod._get_transport()
        except ClaudeCodeError:
            pass

        # Second call must retry and succeed
        t = client_mod._get_transport()
        assert t is not None
        assert call_count[0] == 2


def test_singleton_returns_same_instance():
    mock_transport = MagicMock(spec=MCPTransport)
    with patch("claude_code_orchestrate.client.MCPTransport", return_value=mock_transport):
        client_mod._transport = None
        t1 = client_mod._get_transport()
        t2 = client_mod._get_transport()
        assert t1 is t2


def test_singleton_thread_safe():
    """Concurrent _get_transport calls must create exactly one transport."""
    created = []
    create_lock = threading.Lock()

    class CountingTransport:
        def __init__(self):
            with create_lock:
                created.append(1)
            self._proc = None
            self._request_id = 0
            self._tools = []
            self._lock = threading.Lock()

        def start(self):
            pass

        def stop(self):
            pass

    with patch("claude_code_orchestrate.client.MCPTransport", CountingTransport):
        client_mod._transport = None
        threads = [threading.Thread(target=client_mod._get_transport) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert len(created) == 1
