# claude_code_orchestrate/mcp_transport.py
import json
import subprocess
import threading


class ClaudeCodeError(Exception):
    """Raised when a tool call fails."""
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"{tool_name}: {message}")


class MCPTransport:
    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._request_id = 0
        self._tools: list[dict] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        try:
            self._proc = subprocess.Popen(
                ["claude", "mcp", "serve"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise ClaudeCodeError("transport", "claude CLI not found on PATH") from exc
        # Initialize handshake
        init_result = self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "claude-code-orchestrate", "version": "0.1.0"},
        })
        # Send initialized notification (no response expected)
        self._send_notification("notifications/initialized", {})
        # Discover tools
        tools_result = self._send("tools/list", {})
        self._tools = tools_result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        result = self._send("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        first = content[0] if content else {}
        if not isinstance(first, dict):
            first = {"text": str(first)}
        if result.get("isError"):
            raise ClaudeCodeError(name, first.get("text", "Unknown error"))
        return first.get("text", "")

    def list_tools(self) -> list[dict]:
        return self._tools

    def stop(self) -> None:
        if self._proc:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.stdout.close()
            except Exception:
                pass
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
            self._proc = None

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send(self, method: str, params: dict) -> dict:
        with self._lock:
            req = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": method,
                "params": params,
            }
            self._write(req)
            return self._read_response(req["id"])

    def _send_notification(self, method: str, params: dict) -> None:
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        self._write(msg)

    def _write(self, msg: dict) -> None:
        if self._proc is None:
            raise ClaudeCodeError("transport", "MCP server not running")
        line = json.dumps(msg) + "\n"
        try:
            self._proc.stdin.write(line.encode())
            self._proc.stdin.flush()
        except OSError as exc:
            raise ClaudeCodeError("transport", f"MCP server write failed: {exc}") from exc

    def _read_response(self, expected_id: int) -> dict:
        if self._proc is None:
            raise ClaudeCodeError("transport", "MCP server not running")
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise ClaudeCodeError("transport", "MCP server closed unexpectedly")
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ClaudeCodeError("transport", f"Invalid JSON from MCP server: {exc}") from exc
            # Skip notifications (no id field)
            if "id" not in data:
                continue
            if data["id"] == expected_id:
                if "error" in data:
                    err = data["error"]
                    raise ClaudeCodeError("transport", f"JSON-RPC error {err.get('code')}: {err.get('message')}")
                return data.get("result", {})
