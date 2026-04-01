from unittest.mock import patch, MagicMock
import claude_code_orchestrate.context as ctx_mod


def setup_function():
    """Reset singletons before each test."""
    ctx_mod._client = None
    ctx_mod._server_proc = None
    ctx_mod._project = None


def _mock_agfs():
    client = MagicMock()
    client.health = MagicMock(return_value={"status": "ok"})
    client.mkdir = MagicMock(return_value={})
    return client


def test_init_sets_project_and_creates_dir():
    client = _mock_agfs()
    with patch("claude_code_orchestrate.context.AGFSClient", return_value=client):
        ctx_mod.init("my-project")
        assert ctx_mod._project == "my-project"
        client.mkdir.assert_any_call("/orchestrate")
        client.mkdir.assert_any_call("/orchestrate/my-project")


def test_prefix_raises_without_init():
    from claude_code_orchestrate.mcp_transport import ClaudeCodeError
    try:
        ctx_mod._prefix()
        assert False, "Should have raised"
    except ClaudeCodeError as e:
        assert "init" in str(e).lower()
