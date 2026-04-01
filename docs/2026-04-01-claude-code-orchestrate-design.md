# claude-code-orchestrate SDK Design

## Overview

A Python SDK that makes every Claude Code CLI tool callable as a Python function. Connects to `claude mcp serve` over stdio, exposes 22 tools as module-level functions with signatures matching Claude Code's exact tool names and parameters.

Primary use case: the LLM writes Python scripts that orchestrate Claude Code tools programmatically — loops, conditionals, parallel execution, sub-agent dispatch — instead of making individual tool calls one at a time.

## Architecture

```
Python script (written by LLM, run via Bash)
    │
    ├── from claude_code_orchestrate import Agent, Read, Edit, Bash, ...
    │
    ▼
claude_code_orchestrate/client.py  ── module-level functions (Read, Write, etc.)
    │                                  lazily initialize singleton transport
    ▼
claude_code_orchestrate/mcp_transport.py  ── MCPTransport class
    │                                        spawn subprocess, JSON-RPC 2.0
    ▼
claude mcp serve  ── Claude Code's built-in MCP server (stdio)
    │
    ▼
Claude Code tools (Read, Write, Edit, Bash, Agent, etc.)
```

## Package Structure

```
~/claude-code-orchestrate/
├── claude_code_orchestrate/
│   ├── __init__.py          # re-exports all 22 tool functions
│   ├── client.py            # module-level tool functions + singleton transport
│   └── mcp_transport.py     # stdio MCP client: spawn, JSON-RPC, cleanup
├── tests/
│   └── test_client.py
├── pyproject.toml
└── README.md
```

## MCP Transport Layer (`mcp_transport.py`)

### Class: `MCPTransport`

Manages the `claude mcp serve` subprocess and MCP protocol communication.

```python
class MCPTransport:
    def start(self) -> None
        # 1. Spawn `claude mcp serve` via subprocess.Popen(stdin=PIPE, stdout=PIPE)
        # 2. Send JSON-RPC "initialize" handshake
        # 3. Send "notifications/initialized"
        # 4. Call tools/list to discover available tools

    def call_tool(self, name: str, arguments: dict) -> str
        # 1. Send JSON-RPC "tools/call" request with name + arguments
        # 2. Read response, extract content[0].text
        # 3. Raise ClaudeCodeError on error responses
        # Return: text content from tool result

    def list_tools(self) -> list[dict]
        # Send JSON-RPC "tools/list", return tool definitions

    def stop(self) -> None
        # Kill subprocess, close pipes
```

**Protocol details:**
- JSON-RPC 2.0 over stdio (newline-delimited JSON)
- Blocking send/receive (no async)
- Auto-incrementing request IDs
- `atexit` handler to kill subprocess on process exit

## Client API (`client.py`)

### Singleton Transport

```python
_transport: MCPTransport | None = None

def _get_transport() -> MCPTransport:
    global _transport
    if _transport is None:
        _transport = MCPTransport()
        _transport.start()
        atexit.register(_transport.stop)
    return _transport

def _call(tool_name: str, **kwargs) -> str:
    # Strip None values from kwargs
    args = {k: v for k, v in kwargs.items() if v is not None}
    return _get_transport().call_tool(tool_name, args)
```

### Tool Functions (22 total)

Each function matches Claude Code's exact tool name and parameter signature.

#### File Tools

```python
def Read(file_path: str, offset: int = None, limit: int = None, pages: str = None) -> str:
    return _call("Read", file_path=file_path, offset=offset, limit=limit, pages=pages)

def Write(file_path: str, content: str) -> str:
    return _call("Write", file_path=file_path, content=content)

def Edit(file_path: str, old_string: str, new_string: str, replace_all: bool = None) -> str:
    return _call("Edit", file_path=file_path, old_string=old_string, new_string=new_string, replace_all=replace_all)

def Glob(pattern: str, path: str = None) -> str:
    return _call("Glob", pattern=pattern, path=path)

def Grep(pattern: str, path: str = None, glob: str = None, output_mode: str = None,
         include: str = None, type: str = None, head_limit: int = None, offset: int = None,
         multiline: bool = None, context: int = None) -> str:
    return _call("Grep", pattern=pattern, path=path, glob=glob, output_mode=output_mode,
                 type=type, head_limit=head_limit, offset=offset, multiline=multiline, context=context)
```

#### Execution

```python
def Bash(command: str, timeout: int = None, description: str = None) -> str:
    return _call("Bash", command=command, timeout=timeout, description=description)
```

#### Agent Orchestration

```python
def Agent(description: str, prompt: str, subagent_type: str = None, model: str = None,
          run_in_background: bool = None, name: str = None, team_name: str = None,
          mode: str = None, isolation: str = None) -> str:
    return _call("Agent", description=description, prompt=prompt, subagent_type=subagent_type,
                 model=model, run_in_background=run_in_background, name=name,
                 team_name=team_name, mode=mode, isolation=isolation)

def SendMessage(to: str, message: str, summary: str = None) -> str:
    return _call("SendMessage", to=to, message=message, summary=summary)

def TaskOutput(task_id: str, block: bool = None, timeout: int = None) -> str:
    return _call("TaskOutput", task_id=task_id, block=block, timeout=timeout)

def TaskStop(task_id: str = None, shell_id: str = None) -> str:
    return _call("TaskStop", task_id=task_id, shell_id=shell_id)
```

#### Web

```python
def WebFetch(url: str, prompt: str) -> str:
    return _call("WebFetch", url=url, prompt=prompt)

def WebSearch(query: str, allowed_domains: list = None, blocked_domains: list = None) -> str:
    return _call("WebSearch", query=query, allowed_domains=allowed_domains, blocked_domains=blocked_domains)
```

#### Scheduling

```python
def CronCreate(cron: str, prompt: str, recurring: bool = None, durable: bool = None) -> str:
    return _call("CronCreate", cron=cron, prompt=prompt, recurring=recurring, durable=durable)

def CronDelete(id: str) -> str:
    return _call("CronDelete", id=id)

def CronList() -> str:
    return _call("CronList")
```

#### Teams

```python
def TeamCreate(team_name: str, description: str = None, agent_type: str = None) -> str:
    return _call("TeamCreate", team_name=team_name, description=description, agent_type=agent_type)

def TeamDelete() -> str:
    return _call("TeamDelete")
```

#### Remote

```python
def RemoteTrigger(action: str, trigger_id: str = None, body: str = None) -> str:
    return _call("RemoteTrigger", action=action, trigger_id=trigger_id, body=body)
```

#### Worktree

```python
def EnterWorktree(name: str) -> str:
    return _call("EnterWorktree", name=name)

def ExitWorktree(action: str, discard_changes: bool = None) -> str:
    return _call("ExitWorktree", action=action, discard_changes=discard_changes)
```

#### Misc

```python
def Skill(skill: str, args: str = None) -> str:
    return _call("Skill", skill=skill, args=args)

def ToolSearch(query: str, max_results: int = None) -> str:
    return _call("ToolSearch", query=query, max_results=max_results)

def NotebookEdit(notebook_path: str, new_source: str, cell_id: str = None,
                 cell_type: str = None, edit_mode: str = None) -> str:
    return _call("NotebookEdit", notebook_path=notebook_path, new_source=new_source,
                 cell_id=cell_id, cell_type=cell_type, edit_mode=edit_mode)
```

## Error Handling

```python
class ClaudeCodeError(Exception):
    """Raised when a tool call fails."""
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        super().__init__(f"{tool_name}: {message}")
```

Raised when:
- MCP server returns a JSON-RPC error
- Tool result contains `isError: true`
- Subprocess dies unexpectedly
- Transport fails to connect

## Usage Examples

### Basic file operations
```python
from claude_code_orchestrate import Read, Edit, Glob

for f in Glob(pattern="src/**/*.py").splitlines():
    content = Read(file_path=f)
    if "print(" in content:
        Edit(file_path=f, old_string="print(", new_string="logger.info(", replace_all=True)
```

### Sub-agent orchestration
```python
from claude_code_orchestrate import Agent, SendMessage

# Spawn parallel agents
Agent(description="Fix auth", prompt="Fix auth bugs in src/api/auth.py", name="auth-fixer", run_in_background=True)
Agent(description="Fix tests", prompt="Fix failing tests in tests/", name="test-fixer", run_in_background=True)

# Coordinate
SendMessage(to="auth-fixer", message="are you done?")
```

### Scheduled tasks
```python
from claude_code_orchestrate import CronCreate, CronList

CronCreate(cron="0 9 * * 1", prompt="Review open PRs and summarize status")
print(CronList())
```

## Dependencies

- Python 3.10+
- `claude` CLI installed and on PATH
- No third-party Python dependencies (stdlib only: subprocess, json, atexit, threading)

## Out of Scope

- Async API (sync-only for simplicity)
- Tool schema validation (trust Claude Code's MCP server)
- Skipped tools: `EnterPlanMode`, `ExitPlanMode`, `TodoWrite`, `AskUserQuestion`
