# tests/test_transport.py
import subprocess
from unittest.mock import patch, MagicMock
from claude_code_orchestrate.mcp_transport import MCPTransport, ClaudeCodeError


def _mock_popen(responses: list[str]):
    """Create a mock Popen that returns pre-canned JSON-RPC responses."""
    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.stdout = MagicMock()
    proc.stdout.readline = MagicMock(side_effect=[
        (r + "\n").encode() for r in responses
    ])
    proc.poll = MagicMock(return_value=None)
    proc.pid = 12345
    return proc


def test_start_sends_initialize_handshake():
    init_response = '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"claude","version":"1.0"}}}'
    tools_response = '{"jsonrpc":"2.0","id":2,"result":{"tools":[]}}'

    with patch("subprocess.Popen", return_value=_mock_popen([init_response, tools_response])) as mock_popen:
        transport = MCPTransport()
        transport.start()

        mock_popen.assert_called_once()
        args = mock_popen.call_args
        assert args[0][0] == ["claude", "mcp", "serve"]

        # Should have written initialize request + notification + tools/list
        assert transport._proc.stdin.write.call_count == 3
        transport.stop()


def test_call_tool_returns_text_content():
    init_response = '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"claude","version":"1.0"}}}'
    tools_response = '{"jsonrpc":"2.0","id":2,"result":{"tools":[]}}'
    tool_result = '{"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"file contents here"}]}}'

    proc = _mock_popen([init_response, tools_response, tool_result])
    with patch("subprocess.Popen", return_value=proc):
        transport = MCPTransport()
        transport.start()
        result = transport.call_tool("Read", {"file_path": "/tmp/test.txt"})
        assert result == "file contents here"
        transport.stop()


def test_call_tool_raises_on_error():
    init_response = '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"claude","version":"1.0"}}}'
    tools_response = '{"jsonrpc":"2.0","id":2,"result":{"tools":[]}}'
    error_result = '{"jsonrpc":"2.0","id":3,"result":{"isError":true,"content":[{"type":"text","text":"file not found"}]}}'

    proc = _mock_popen([init_response, tools_response, error_result])
    with patch("subprocess.Popen", return_value=proc):
        transport = MCPTransport()
        transport.start()
        try:
            transport.call_tool("Read", {"file_path": "/nonexistent"})
            assert False, "Should have raised"
        except ClaudeCodeError as e:
            assert "file not found" in str(e)
            assert e.tool_name == "Read"
        transport.stop()
