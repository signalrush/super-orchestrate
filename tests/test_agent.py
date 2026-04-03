"""Tests for Agent function — async/sync bridge, definition resolution, SDK options."""
import asyncio
import concurrent.futures
from unittest.mock import patch, MagicMock
import pytest

import claude_code_orchestrate.client as client_mod
from claude_agent_sdk import AgentDefinition


def _make_mock_query(result_text="done"):
    mock_result = MagicMock()
    mock_result.result = result_text

    async def mock_query(*args, **kwargs):
        mock_query.last_kwargs = kwargs
        yield mock_result

    return mock_query, mock_result


def setup_function():
    client_mod._agent_defs = {}
    client_mod._transport = None


# --- Basic functionality ---

def test_agent_returns_result_text():
    mock_query, mock_result = _make_mock_query("agent output")
    with patch("claude_code_orchestrate.client.query", side_effect=mock_query):
        with patch("claude_code_orchestrate.client.ResultMessage", type(mock_result)):
            result = client_mod.Agent(description="test", prompt="hello")
            assert result == "agent output"


def test_agent_returns_empty_on_no_result_message():
    async def empty_query(*args, **kwargs):
        return
        yield

    with patch("claude_code_orchestrate.client.query", side_effect=empty_query):
        with patch("claude_code_orchestrate.client.ResultMessage", MagicMock):
            result = client_mod.Agent(description="test", prompt="hello")
            assert result == ""


def test_agent_bypasses_mcp_transport():
    mock_query, mock_result = _make_mock_query()
    transport = MagicMock()
    with patch.object(client_mod, "_transport", transport):
        with patch("claude_code_orchestrate.client.query", side_effect=mock_query):
            with patch("claude_code_orchestrate.client.ResultMessage", type(mock_result)):
                client_mod.Agent(description="test", prompt="hello")
                transport.call_tool.assert_not_called()


# --- Model resolution ---

def test_agent_explicit_model_passed_to_sdk():
    mock_query, mock_result = _make_mock_query()
    with patch("claude_code_orchestrate.client.query", side_effect=mock_query):
        with patch("claude_code_orchestrate.client.ResultMessage", type(mock_result)):
            client_mod.Agent(description="test", prompt="hello", model="opus")
            assert mock_query.last_kwargs["options"].model == "opus"


def test_agent_model_from_definition():
    client_mod._agent_defs = {
        "researcher": AgentDefinition(description="R", prompt="P", tools=None, model="haiku"),
    }
    mock_query, mock_result = _make_mock_query()
    with patch("claude_code_orchestrate.client.query", side_effect=mock_query):
        with patch("claude_code_orchestrate.client.ResultMessage", type(mock_result)):
            client_mod.Agent(description="test", prompt="hello", subagent_type="researcher")
            assert mock_query.last_kwargs["options"].model == "haiku"


def test_agent_explicit_model_overrides_definition():
    client_mod._agent_defs = {
        "agent": AgentDefinition(description="A", prompt="P", tools=None, model="haiku"),
    }
    mock_query, mock_result = _make_mock_query()
    with patch("claude_code_orchestrate.client.query", side_effect=mock_query):
        with patch("claude_code_orchestrate.client.ResultMessage", type(mock_result)):
            client_mod.Agent(description="t", prompt="p", subagent_type="agent", model="opus")
            assert mock_query.last_kwargs["options"].model == "opus"


def test_agent_inherit_model_resolves_to_none():
    client_mod._agent_defs = {
        "agent": AgentDefinition(description="A", prompt="P", tools=None, model="inherit"),
    }
    mock_query, mock_result = _make_mock_query()
    with patch("claude_code_orchestrate.client.query", side_effect=mock_query):
        with patch("claude_code_orchestrate.client.ResultMessage", type(mock_result)):
            client_mod.Agent(description="t", prompt="p", subagent_type="agent")
            assert mock_query.last_kwargs["options"].model is None


# --- Tools resolution ---

def test_agent_tools_from_definition():
    client_mod._agent_defs = {
        "coder": AgentDefinition(description="C", prompt="P", tools=["Read", "Write"], model="inherit"),
    }
    mock_query, mock_result = _make_mock_query()
    with patch("claude_code_orchestrate.client.query", side_effect=mock_query):
        with patch("claude_code_orchestrate.client.ResultMessage", type(mock_result)):
            client_mod.Agent(description="t", prompt="p", subagent_type="coder")
            assert mock_query.last_kwargs["options"].allowed_tools == ["Read", "Write"]


def test_agent_unknown_subagent_type_uses_no_definition():
    client_mod._agent_defs = {"known": AgentDefinition(description="K", prompt="P", tools=["Read"], model="sonnet")}
    mock_query, mock_result = _make_mock_query()
    with patch("claude_code_orchestrate.client.query", side_effect=mock_query):
        with patch("claude_code_orchestrate.client.ResultMessage", type(mock_result)):
            client_mod.Agent(description="t", prompt="p", subagent_type="unknown")
            opts = mock_query.last_kwargs["options"]
            assert opts.model is None
            assert opts.system_prompt is None


# --- System prompt ---

def test_agent_system_prompt_from_definition():
    client_mod._agent_defs = {
        "agent": AgentDefinition(description="A", prompt="You are a helper.", tools=None, model="inherit"),
    }
    mock_query, mock_result = _make_mock_query()
    with patch("claude_code_orchestrate.client.query", side_effect=mock_query):
        with patch("claude_code_orchestrate.client.ResultMessage", type(mock_result)):
            client_mod.Agent(description="t", prompt="p", subagent_type="agent")
            sp = mock_query.last_kwargs["options"].system_prompt
            assert sp == {"type": "preset", "preset": "claude_code", "append": "You are a helper."}


# --- Async/sync bridge ---

def test_agent_runtime_error_from_sdk_propagates():
    """RuntimeError from the SDK must not be swallowed."""
    async def bad_query(*args, **kwargs):
        raise RuntimeError("SDK internal error")
        yield

    with patch("claude_code_orchestrate.client.query", side_effect=bad_query):
        with patch("claude_code_orchestrate.client.ResultMessage", MagicMock):
            with pytest.raises(RuntimeError, match="SDK internal error"):
                client_mod.Agent(description="t", prompt="p")


def test_agent_works_from_async_context():
    """Agent should work when called from within a running event loop."""
    mock_query, mock_result = _make_mock_query("async result")

    async def async_caller():
        with patch("claude_code_orchestrate.client.query", side_effect=mock_query):
            with patch("claude_code_orchestrate.client.ResultMessage", type(mock_result)):
                return client_mod.Agent(description="t", prompt="p")

    # Run in a separate thread to get a clean event loop
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(asyncio.run, async_caller())
        assert future.result() == "async result"


# --- Resolve by name ---

def test_agent_resolves_by_name():
    client_mod._agent_defs = {
        "my-agent": AgentDefinition(description="A", prompt="You are my agent.", tools=["Bash"], model="sonnet"),
    }
    mock_query, mock_result = _make_mock_query()
    with patch("claude_code_orchestrate.client.query", side_effect=mock_query):
        with patch("claude_code_orchestrate.client.ResultMessage", type(mock_result)):
            client_mod.Agent(description="t", prompt="p", name="my-agent")
            opts = mock_query.last_kwargs["options"]
            assert opts.model == "sonnet"
            assert opts.allowed_tools == ["Bash"]
