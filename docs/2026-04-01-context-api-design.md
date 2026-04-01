# Context API Design (OpenViking Integration)

## Overview

Add a `ctx` module to claude-code-orchestrate that provides persistent, project-scoped context management backed by OpenViking's virtual filesystem. Enables orchestration scripts to store, retrieve, search, and manage context between agents without blowing up context windows.

The key insight: code manipulates context as a **zero-cost data plane** — filtering, routing, and transforming data between agents without burning LLM tokens. The context store makes this persistent and searchable.

## Architecture

```
ctx.put("analysis", data)
    │
    ▼
claude_code_orchestrate/context.py   ── 6 module-level functions
    │                                    lazy-connect AGFSClient singleton
    ▼
AGFSClient (openviking SDK)          ── filesystem operations
    │
    ▼
openviking-server (localhost:1933)   ── auto-started if not running
    │
    ▼
viking:///orchestrate/{project}/     ── persistent filesystem storage
```

## File Structure

```
claude_code_orchestrate/
├── context.py        # NEW: ctx module — 6 functions + server management
├── client.py         # existing: tool functions
├── mcp_transport.py  # existing: MCP stdio transport
└── __init__.py       # updated: add ctx re-export
```

## Auto-Start Logic

```python
_client: AGFSClient | None = None
_server_proc: subprocess.Popen | None = None

def _ensure_server() -> AGFSClient:
    global _client, _server_proc
    if _client is not None:
        return _client

    # 1. Try connecting to existing server
    client = AGFSClient("http://localhost:1933")
    try:
        client.health()
        _client = client
        return _client
    except Exception:
        pass

    # 2. Server not running — spawn it
    _server_proc = subprocess.Popen(
        ["openviking-server"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    atexit.register(_stop_server)

    # 3. Wait for health check (up to 5s)
    for _ in range(50):
        try:
            client.health()
            _client = client
            return _client
        except Exception:
            time.sleep(0.1)

    raise ClaudeCodeError("ctx", "Failed to start openviking-server")
```

## Project Scoping

All context lives under `/orchestrate/{project}/` in the OpenViking filesystem.

```python
_project: str | None = None

def init(project: str) -> None:
    """Set the active project scope. Required before any other ctx call."""
    global _project
    _project = project
    client = _ensure_server()
    # Ensure project directory exists
    try:
        client.mkdir(f"/orchestrate/{project}")
    except Exception:
        pass  # already exists

def _prefix() -> str:
    if _project is None:
        raise ClaudeCodeError("ctx", "Call ctx.init(project_name) first")
    return f"/orchestrate/{_project}"
```

## API: 6 Functions

### `init(project: str) -> None`

Set the active project scope. Creates the project directory if it doesn't exist. Must be called before any other ctx function.

```python
ctx.init("refactor-auth")
```

### `put(key: str, value: str) -> None`

Store context at key, relative to project scope. Creates intermediate directories automatically.

```python
def put(key: str, value: str) -> None:
    client = _ensure_server()
    path = f"{_prefix()}/{key}"
    # Ensure parent directory exists
    parent = "/".join(path.split("/")[:-1])
    if parent:
        try:
            client.mkdir(parent)
        except Exception:
            pass
    client.write(path, value.encode())
```

### `get(key: str) -> str`

Retrieve context by key.

```python
def get(key: str) -> str:
    client = _ensure_server()
    path = f"{_prefix()}/{key}"
    data = client.cat(path)
    if isinstance(data, bytes):
        return data.decode()
    return str(data)
```

### `ls(prefix: str = "") -> list[str]`

List stored context keys under the given prefix.

```python
def ls(prefix: str = "") -> list[str]:
    client = _ensure_server()
    path = f"{_prefix()}/{prefix}".rstrip("/")
    entries = client.ls(path)
    return [e["name"] for e in entries]
```

### `search(query: str) -> str`

Search across all stored context in the project. Returns matching content.

```python
def search(query: str) -> str:
    client = _ensure_server()
    results = client.grep(_prefix(), query, recursive=True)
    if isinstance(results, bytes):
        return results.decode()
    return str(results)
```

### `rm(key: str, recursive: bool = False) -> None`

Remove context by key.

```python
def rm(key: str, recursive: bool = False) -> None:
    client = _ensure_server()
    path = f"{_prefix()}/{key}"
    client.rm(path, recursive=recursive)
```

## __init__.py Update

```python
from claude_code_orchestrate import context as ctx

__all__ = [
    # existing 23 tools + ClaudeCodeError...
    "ctx",
]
```

## Error Handling

All ctx functions raise `ClaudeCodeError` (already defined in mcp_transport.py) on:
- Server connection failure
- `init()` not called before other functions
- Key not found on `get()`
- OpenViking filesystem errors

## Usage Example

```python
from claude_code_orchestrate import Agent, Glob, Read, ctx

ctx.init("codebase-migration")

# Phase 1: Code filters files — zero tokens
for f in Glob(pattern="src/**/*.py"):
    content = Read(file_path=f)
    if "deprecated" in content:
        ctx.put(f"deprecated/{f}", content)

# Phase 2: Agent gets only relevant context
files = ctx.ls("deprecated/")
analysis = Agent(prompt=f"Analyze these deprecated files: {files}")
ctx.put("analysis", analysis)

# Phase 3: Different agent reads compressed analysis
Agent(prompt=f"Create migration plan:\n{ctx.get('analysis')}")

# Phase 4: Search for specific patterns
relevant = ctx.search("security vulnerability")
Agent(prompt=f"Fix security issues:\n{relevant}")
```

## Dependencies

- `openviking` (pip install openviking) — already installed
- `openviking-server` binary on PATH (comes with openviking package)

## Out of Scope

- L0/L1/L2 tier selection (OpenViking handles this internally)
- Async API
- Cross-project context sharing
- Context expiration/TTL
