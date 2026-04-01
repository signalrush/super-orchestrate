from unittest.mock import patch, MagicMock
import claude_code_orchestrate.client as client_mod


def _mock_transport():
    transport = MagicMock()
    transport.call_tool = MagicMock(return_value="mock result")
    return transport


def setup_function():
    """Reset singleton before each test."""
    client_mod._transport = None


def test_read_calls_transport_with_correct_args():
    transport = _mock_transport()
    with patch.object(client_mod, "_transport", transport):
        from claude_code_orchestrate.client import Read
        result = Read(file_path="/tmp/test.py")
        transport.call_tool.assert_called_once_with("Read", {"file_path": "/tmp/test.py"})
        assert result == "mock result"


def test_read_strips_none_optional_args():
    transport = _mock_transport()
    with patch.object(client_mod, "_transport", transport):
        from claude_code_orchestrate.client import Read
        Read(file_path="/tmp/test.py", offset=None, limit=10)
        transport.call_tool.assert_called_once_with("Read", {"file_path": "/tmp/test.py", "limit": 10})


def test_agent_passes_all_params():
    transport = _mock_transport()
    with patch.object(client_mod, "_transport", transport):
        from claude_code_orchestrate.client import Agent
        Agent(description="fix bugs", prompt="fix all bugs", model="sonnet", run_in_background=True)
        transport.call_tool.assert_called_once_with("Agent", {
            "description": "fix bugs",
            "prompt": "fix all bugs",
            "model": "sonnet",
            "run_in_background": True,
        })


def test_bash_with_timeout():
    transport = _mock_transport()
    with patch.object(client_mod, "_transport", transport):
        from claude_code_orchestrate.client import Bash
        Bash(command="echo hello", timeout=5000)
        transport.call_tool.assert_called_once_with("Bash", {
            "command": "echo hello",
            "timeout": 5000,
        })
