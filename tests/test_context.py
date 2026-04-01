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


def test_put_writes_to_correct_path():
    client = _mock_agfs()
    with patch("claude_code_orchestrate.context.AGFSClient", return_value=client):
        ctx_mod.init("test-proj")
        ctx_mod.put("analysis", "some findings")
        client.write.assert_called_once_with("/orchestrate/test-proj/analysis", b"some findings")


def test_put_creates_parent_dirs():
    client = _mock_agfs()
    with patch("claude_code_orchestrate.context.AGFSClient", return_value=client):
        ctx_mod.init("test-proj")
        ctx_mod.put("phase-1/findings", "data")
        client.mkdir.assert_any_call("/orchestrate/test-proj/phase-1")


def test_get_reads_from_correct_path():
    client = _mock_agfs()
    client.cat = MagicMock(return_value=b"stored content")
    with patch("claude_code_orchestrate.context.AGFSClient", return_value=client):
        ctx_mod.init("test-proj")
        result = ctx_mod.get("analysis")
        client.cat.assert_called_once_with("/orchestrate/test-proj/analysis")
        assert result == "stored content"


def test_put_get_roundtrip():
    client = _mock_agfs()
    stored = {}

    def fake_write(path, data):
        stored[path] = data
        return path

    def fake_cat(path):
        return stored[path]

    client.write = MagicMock(side_effect=fake_write)
    client.cat = MagicMock(side_effect=fake_cat)

    with patch("claude_code_orchestrate.context.AGFSClient", return_value=client):
        ctx_mod.init("test-proj")
        ctx_mod.put("key", "hello world")
        result = ctx_mod.get("key")
        assert result == "hello world"


def test_ls_returns_names():
    client = _mock_agfs()
    client.ls = MagicMock(return_value=[
        {"name": "analysis"},
        {"name": "phase-1"},
    ])
    with patch("claude_code_orchestrate.context.AGFSClient", return_value=client):
        ctx_mod.init("test-proj")
        result = ctx_mod.ls()
        client.ls.assert_called_once_with("/orchestrate/test-proj")
        assert result == ["analysis", "phase-1"]


def test_ls_with_prefix():
    client = _mock_agfs()
    client.ls = MagicMock(return_value=[{"name": "findings"}])
    with patch("claude_code_orchestrate.context.AGFSClient", return_value=client):
        ctx_mod.init("test-proj")
        result = ctx_mod.ls("phase-1/")
        client.ls.assert_called_once_with("/orchestrate/test-proj/phase-1")
        assert result == ["findings"]


def test_search_greps_project():
    client = _mock_agfs()
    client.grep = MagicMock(return_value=b"line1: match\nline2: match")
    with patch("claude_code_orchestrate.context.AGFSClient", return_value=client):
        ctx_mod.init("test-proj")
        result = ctx_mod.search("match")
        client.grep.assert_called_once_with("/orchestrate/test-proj", "match", recursive=True)
        assert "match" in result


def test_rm_removes_key():
    client = _mock_agfs()
    client.rm = MagicMock(return_value={})
    with patch("claude_code_orchestrate.context.AGFSClient", return_value=client):
        ctx_mod.init("test-proj")
        ctx_mod.rm("analysis")
        client.rm.assert_called_once_with("/orchestrate/test-proj/analysis", recursive=False)


def test_rm_recursive():
    client = _mock_agfs()
    client.rm = MagicMock(return_value={})
    with patch("claude_code_orchestrate.context.AGFSClient", return_value=client):
        ctx_mod.init("test-proj")
        ctx_mod.rm("phase-1/", recursive=True)
        client.rm.assert_called_once_with("/orchestrate/test-proj/phase-1/", recursive=True)
