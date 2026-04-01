import atexit
import subprocess
import time

from openviking import AGFSClient
from claude_code_orchestrate.mcp_transport import ClaudeCodeError

_client: AGFSClient | None = None
_server_proc: subprocess.Popen | None = None
_project: str | None = None


def _stop_server() -> None:
    global _server_proc
    if _server_proc:
        try:
            _server_proc.terminate()
            _server_proc.wait(timeout=5)
        except Exception:
            _server_proc.kill()
        _server_proc = None


def _ensure_server() -> AGFSClient:
    global _client, _server_proc
    if _client is not None:
        return _client

    client = AGFSClient("http://localhost:1933")
    try:
        client.health()
        _client = client
        return _client
    except Exception:
        pass

    _server_proc = subprocess.Popen(
        ["openviking-server"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    atexit.register(_stop_server)

    for _ in range(50):
        try:
            client.health()
            _client = client
            return _client
        except Exception:
            time.sleep(0.1)

    raise ClaudeCodeError("ctx", "Failed to start openviking-server")


def _prefix() -> str:
    if _project is None:
        raise ClaudeCodeError("ctx", "Call ctx.init(project_name) first")
    return f"/orchestrate/{_project}"


def init(project: str) -> None:
    """Set the active project scope. Required before any other ctx call."""
    global _project
    _project = project
    client = _ensure_server()
    try:
        client.mkdir("/orchestrate")
    except Exception:
        pass
    try:
        client.mkdir(f"/orchestrate/{project}")
    except Exception:
        pass
