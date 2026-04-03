"""Extended transport tests — error handling, thread safety, edge cases."""
import json
import subprocess
import threading
from unittest.mock import patch, MagicMock

from claude_code_orchestrate.mcp_transport import MCPTransport, ClaudeCodeError


# --- Error handling ---

def test_call_tool_empty_error_content():
    """isError with empty content list must not IndexError."""
    proc = MagicMock()
    resp = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "result": {"isError": True, "content": []},
    }).encode() + b"\n"
    proc.stdout.readline = MagicMock(return_value=resp)

    transport = MCPTransport()
    transport._proc = proc
    transport._request_id = 0
    try:
        transport.call_tool("Read", {"file_path": "/test"})
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert "Unknown error" in str(e)
        assert e.tool_name == "Read"


def test_call_tool_no_content_key_on_error():
    proc = MagicMock()
    resp = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "result": {"isError": True},
    }).encode() + b"\n"
    proc.stdout.readline = MagicMock(return_value=resp)

    transport = MCPTransport()
    transport._proc = proc
    transport._request_id = 0
    try:
        transport.call_tool("Read", {"file_path": "/test"})
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert "Unknown error" in str(e)


def test_write_broken_pipe_wrapped():
    """BrokenPipeError from stdin must be wrapped in ClaudeCodeError."""
    transport = MCPTransport()
    proc = MagicMock()
    proc.stdin.write = MagicMock(side_effect=BrokenPipeError("broken"))
    transport._proc = proc

    try:
        transport._write({"jsonrpc": "2.0", "id": 1, "method": "test", "params": {}})
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert e.tool_name == "transport"
        assert "write failed" in str(e)


def test_write_flush_broken_pipe_wrapped():
    transport = MCPTransport()
    proc = MagicMock()
    proc.stdin.write = MagicMock()
    proc.stdin.flush = MagicMock(side_effect=BrokenPipeError("flush"))
    transport._proc = proc

    try:
        transport._write({"jsonrpc": "2.0", "id": 1, "method": "test", "params": {}})
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert "write failed" in str(e)


def test_write_oserror_wrapped():
    """Non-BrokenPipeError OSError (e.g. bad file descriptor) must also be wrapped."""
    transport = MCPTransport()
    proc = MagicMock()
    proc.stdin.write = MagicMock(side_effect=OSError("Bad file descriptor"))
    transport._proc = proc

    try:
        transport._write({"jsonrpc": "2.0", "id": 1, "method": "test", "params": {}})
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert e.tool_name == "transport"
        assert "Bad file descriptor" in str(e)


def test_write_raises_when_proc_is_none():
    transport = MCPTransport()
    assert transport._proc is None
    try:
        transport._write({"jsonrpc": "2.0", "id": 1, "method": "test", "params": {}})
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert "not running" in str(e)


def test_read_response_raises_when_proc_is_none():
    transport = MCPTransport()
    assert transport._proc is None
    try:
        transport._read_response(1)
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert "not running" in str(e)


def test_call_tool_on_stopped_transport():
    transport = MCPTransport()
    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.stdout = MagicMock()
    proc.terminate = MagicMock()
    proc.wait = MagicMock()
    transport._proc = proc
    transport.stop()

    try:
        transport.call_tool("Read", {"file_path": "/f"})
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert "not running" in str(e)


# --- _read_response edge cases ---

def test_read_response_skips_notifications():
    proc = MagicMock()
    lines = [
        json.dumps({"jsonrpc": "2.0", "method": "notif", "params": {}}).encode() + b"\n",
        json.dumps({"jsonrpc": "2.0", "id": 5, "result": {"data": "found"}}).encode() + b"\n",
    ]
    proc.stdout.readline = MagicMock(side_effect=lines)

    transport = MCPTransport()
    transport._proc = proc
    result = transport._read_response(5)
    assert result == {"data": "found"}


def test_read_response_skips_mismatched_ids():
    proc = MagicMock()
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 99, "result": {}}).encode() + b"\n",
        json.dumps({"jsonrpc": "2.0", "id": 5, "result": {"ok": True}}).encode() + b"\n",
    ]
    proc.stdout.readline = MagicMock(side_effect=lines)

    transport = MCPTransport()
    transport._proc = proc
    result = transport._read_response(5)
    assert result == {"ok": True}


def test_read_response_raises_on_eof():
    proc = MagicMock()
    proc.stdout.readline = MagicMock(return_value=b"")

    transport = MCPTransport()
    transport._proc = proc
    try:
        transport._read_response(1)
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert "closed unexpectedly" in str(e)


def test_read_response_raises_on_invalid_json():
    proc = MagicMock()
    proc.stdout.readline = MagicMock(return_value=b"not json\n")

    transport = MCPTransport()
    transport._proc = proc
    try:
        transport._read_response(1)
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert "Invalid JSON" in str(e)


def test_read_response_raises_on_jsonrpc_error():
    proc = MagicMock()
    resp = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "error": {"code": -32600, "message": "Invalid Request"},
    }).encode() + b"\n"
    proc.stdout.readline = MagicMock(return_value=resp)

    transport = MCPTransport()
    transport._proc = proc
    try:
        transport._read_response(1)
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert "-32600" in str(e)


# --- Thread safety ---

def test_send_is_thread_safe():
    """Concurrent _send calls must produce unique IDs and valid JSON."""
    transport = MCPTransport()
    proc = MagicMock()

    written = []
    write_lock = threading.Lock()

    def tracking_write(data):
        with write_lock:
            written.append(data)

    proc.stdin.write = tracking_write
    proc.stdin.flush = MagicMock()

    response_id = [0]
    resp_lock = threading.Lock()

    def make_response():
        with resp_lock:
            response_id[0] += 1
            rid = response_id[0]
        return json.dumps({"jsonrpc": "2.0", "id": rid, "result": {}}).encode() + b"\n"

    proc.stdout.readline = MagicMock(side_effect=lambda: make_response())
    transport._proc = proc

    errors = []

    def call_send(tid):
        try:
            transport._send("tools/call", {"tid": tid})
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=call_send, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    # All writes are valid JSON
    for w in written:
        json.loads(w.decode())
    # All IDs are unique
    ids = [json.loads(w.decode())["id"] for w in written]
    assert len(set(ids)) == len(ids)


# --- stop() ---

def test_stop_with_no_process():
    transport = MCPTransport()
    transport.stop()  # must not raise


def test_stop_falls_back_to_kill():
    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.stdout = MagicMock()
    proc.terminate = MagicMock()
    proc.wait = MagicMock(side_effect=Exception("timeout"))
    proc.kill = MagicMock()

    transport = MCPTransport()
    transport._proc = proc
    transport.stop()

    proc.kill.assert_called_once()
    assert transport._proc is None


def test_stop_handles_stdin_close_error():
    proc = MagicMock()
    proc.stdin.close = MagicMock(side_effect=OSError("already closed"))
    proc.stdout = MagicMock()
    proc.terminate = MagicMock()
    proc.wait = MagicMock()

    transport = MCPTransport()
    transport._proc = proc
    transport.stop()
    assert transport._proc is None


# --- start() errors ---

def test_start_wraps_file_not_found():
    """Missing claude CLI must raise ClaudeCodeError, not raw FileNotFoundError."""
    with patch("subprocess.Popen", side_effect=FileNotFoundError("claude")):
        transport = MCPTransport()
        try:
            transport.start()
            assert False, "Should have raised"
        except ClaudeCodeError as e:
            assert "not found" in str(e)
            assert e.tool_name == "transport"


# --- call_tool with non-dict content items ---

def test_call_tool_string_content_item():
    proc = MagicMock()
    resp = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "result": {"content": ["just a string"]},
    }).encode() + b"\n"
    proc.stdout.readline = MagicMock(return_value=resp)

    transport = MCPTransport()
    transport._proc = proc
    transport._request_id = 0
    result = transport.call_tool("Bash", {"command": "echo"})
    assert result == "just a string"


def test_call_tool_none_content_item():
    proc = MagicMock()
    resp = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "result": {"content": [None]},
    }).encode() + b"\n"
    proc.stdout.readline = MagicMock(return_value=resp)

    transport = MCPTransport()
    transport._proc = proc
    transport._request_id = 0
    result = transport.call_tool("Bash", {"command": "echo"})
    assert isinstance(result, str)


def test_call_tool_int_content_item():
    proc = MagicMock()
    resp = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "result": {"content": [42]},
    }).encode() + b"\n"
    proc.stdout.readline = MagicMock(return_value=resp)

    transport = MCPTransport()
    transport._proc = proc
    transport._request_id = 0
    result = transport.call_tool("Bash", {"command": "echo"})
    assert result == "42"


def test_call_tool_error_with_string_content_item():
    proc = MagicMock()
    resp = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "result": {"isError": True, "content": ["error text"]},
    }).encode() + b"\n"
    proc.stdout.readline = MagicMock(return_value=resp)

    transport = MCPTransport()
    transport._proc = proc
    transport._request_id = 0
    try:
        transport.call_tool("Read", {"file_path": "/f"})
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert "error text" in str(e)
