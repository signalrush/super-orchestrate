# claude-code-orchestrate

Python SDK that makes every Claude Code CLI tool callable as a Python function.

## Install

```bash
pip install -e .
```

Requires `claude` CLI installed and on PATH.

## Usage

```python
from claude_code_orchestrate import Read, Edit, Glob, Grep, Bash, Agent, SendMessage, CronCreate

# File operations
content = Read(file_path="src/main.py")
Edit(file_path="src/main.py", old_string="print(", new_string="logger.info(", replace_all=True)

# Search
files = Glob(pattern="src/**/*.py")
matches = Grep(pattern="TODO", path="src/")

# Shell
output = Bash(command="npm test")

# Sub-agent orchestration
result = Agent(
    description="Fix auth bugs",
    prompt="Find and fix all authentication bugs in src/api/",
)

# Parallel agents
Agent(description="Fix auth", prompt="Fix auth.py", name="a1", run_in_background=True)
Agent(description="Fix tests", prompt="Fix tests/", name="a2", run_in_background=True)
SendMessage(to="a1", message="status?")

# Scheduling
CronCreate(cron="0 9 * * 1", prompt="Review open PRs")
```

Every function name and parameter matches Claude Code's tool signatures exactly.

## How it works

Spawns `claude mcp serve` as a subprocess, communicates via JSON-RPC 2.0 over stdio. Transport is lazily initialized on first call and cleaned up at exit.

## All tools

**File:** `Read`, `Write`, `Edit`, `Glob`, `Grep`
**Execution:** `Bash`
**Agent:** `Agent`, `SendMessage`, `TaskOutput`, `TaskStop`
**Web:** `WebFetch`, `WebSearch`
**Scheduling:** `CronCreate`, `CronDelete`, `CronList`
**Teams:** `TeamCreate`, `TeamDelete`
**Remote:** `RemoteTrigger`
**Worktree:** `EnterWorktree`, `ExitWorktree`
**Misc:** `Skill`, `ToolSearch`, `NotebookEdit`

## Context Management

Persistent, project-scoped context store backed by [OpenViking](https://github.com/volcengine/OpenViking). Requires `pip install openviking`.

```python
from claude_code_orchestrate import Agent, Glob, Read, ctx

ctx.init("my-project")

# Store agent results
result = Agent(description="Research", prompt="Analyze the auth system")
ctx.put("analysis", result)

# Retrieve later — even from a different script
analysis = ctx.get("analysis")

# List what's stored
keys = ctx.ls()  # ["analysis"]

# Search across all context
hits = ctx.search("token refresh")

# Clean up
ctx.rm("analysis")
```

Auto-starts `openviking-server` if not running. All context persists across sessions.
