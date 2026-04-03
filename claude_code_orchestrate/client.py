import asyncio
import atexit
import concurrent.futures
import json
import os
import threading
from pathlib import Path

from claude_code_orchestrate.mcp_transport import MCPTransport
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, AgentDefinition

_transport: MCPTransport | None = None
_transport_lock = threading.Lock()
_agent_defs: dict[str, AgentDefinition] | None = None


def _load_agent_definitions() -> dict[str, AgentDefinition]:
    """Load agent definitions from ~/.claude/agents/*.md files."""
    agents_dir = Path.home() / ".claude" / "agents"
    defs = {}
    if not agents_dir.is_dir():
        return defs
    for md_file in agents_dir.glob("*.md"):
        try:
            text = md_file.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        # Strip BOM if present (common on Windows)
        if text.startswith("\ufeff"):
            text = text[1:]
        # Parse YAML frontmatter
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        frontmatter = parts[1].strip()
        body = parts[2].strip()

        # Parse frontmatter fields
        meta = {}
        list_key = None
        list_items = []
        for line in frontmatter.split("\n"):
            stripped = line.lstrip()
            if stripped.startswith("- ") and list_key and line[0] in (" ", "\t"):
                list_items.append(stripped.removeprefix("- ").strip())
                continue
            if list_key and list_items:
                meta[list_key] = list_items
                list_items = []
                list_key = None
            if ":" in line:
                key, _, val = line.partition(":")
                val = val.strip().strip('"').strip("'")
                if val:
                    meta[key.strip()] = val
                else:
                    list_key = key.strip()
            else:
                list_key = None
        if list_key and list_items:
            meta[list_key] = list_items

        name = meta.get("name", md_file.stem)
        if isinstance(name, list):
            name = name[0] if name else md_file.stem
        tools_raw = meta.get("tools", "")
        if isinstance(tools_raw, list):
            tools = tools_raw if tools_raw else None
        else:
            tools = [t.strip() for t in tools_raw.split(",") if t.strip()] if tools_raw else None
        model_val = meta.get("model", "inherit")
        if isinstance(model_val, list):
            model_val = model_val[0] if model_val else "inherit"
        if model_val not in ("sonnet", "opus", "haiku", "inherit"):
            model_val = "inherit"

        desc = meta.get("description", "")
        if isinstance(desc, list):
            desc = " ".join(desc)

        defs[name] = AgentDefinition(
            description=desc,
            prompt=body,
            tools=tools,
            model=model_val,
        )
    return defs


def _get_agent_definitions() -> dict[str, AgentDefinition]:
    global _agent_defs
    if _agent_defs is None:
        _agent_defs = _load_agent_definitions()
    return _agent_defs


def _get_transport() -> MCPTransport:
    global _transport
    with _transport_lock:
        if _transport is None:
            t = MCPTransport()
            t.start()
            _transport = t
            atexit.register(t.stop)
        return _transport


def _parse(tool_name: str, raw: str) -> "str | list[str]":
    """Parse raw MCP JSON response into native Python types."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw

    if tool_name == "Read":
        if isinstance(data, dict) and isinstance(data.get("file"), dict):
            val = data["file"].get("content")
            return val if val is not None else raw
        return raw

    elif tool_name == "Write":
        if isinstance(data, dict) and "filePath" in data:
            val = data["filePath"]
            return val if val is not None else raw
        return raw

    elif tool_name == "Edit":
        if isinstance(data, dict) and isinstance(data.get("structuredPatch"), list):
            lines = []
            for patch in data["structuredPatch"]:
                if isinstance(patch, dict):
                    patch_lines = patch.get("lines")
                    if isinstance(patch_lines, list):
                        lines.extend(patch_lines)
            return "\n".join(lines) if lines else raw
        return raw

    elif tool_name == "Glob":
        if isinstance(data, dict) and "filenames" in data:
            val = data["filenames"]
            return val if val is not None else raw
        return raw

    elif tool_name == "Grep":
        if isinstance(data, dict):
            for key in ("filenames", "content", "counts"):
                if key in data and data[key] is not None:
                    return data[key]
        return raw

    elif tool_name == "Bash":
        if isinstance(data, dict) and "stdout" in data:
            val = data["stdout"]
            return val if val is not None else raw
        return raw

    return raw


def _call(tool_name: str, **kwargs) -> "str | list[str]":
    args = {k: v for k, v in kwargs.items() if v is not None}
    raw = _get_transport().call_tool(tool_name, args)
    return _parse(tool_name, raw)


# --- File Tools ---

def Read(file_path: str, offset: int = None, limit: int = None, pages: str = None) -> str:
    return _call("Read", file_path=file_path, offset=offset, limit=limit, pages=pages)


def Write(file_path: str, content: str) -> str:
    return _call("Write", file_path=file_path, content=content)


def Edit(file_path: str, old_string: str, new_string: str, replace_all: bool = None) -> str:
    return _call("Edit", file_path=file_path, old_string=old_string, new_string=new_string, replace_all=replace_all)


def Glob(pattern: str, path: str = None) -> "str | list[str]":
    return _call("Glob", pattern=pattern, path=path)


def Grep(pattern: str, path: str = None, glob: str = None, output_mode: str = None,
         type: str = None, head_limit: int = None, offset: int = None,
         multiline: bool = None, context: int = None,
         case_insensitive: bool = None, after_context: int = None,
         before_context: int = None, context_alias: int = None,
         line_numbers: bool = None) -> "str | list[str]":
    kwargs = {
        "pattern": pattern, "path": path, "glob": glob, "output_mode": output_mode,
        "type": type, "head_limit": head_limit, "offset": offset,
        "multiline": multiline, "context": context,
        "-i": case_insensitive, "-A": after_context,
        "-B": before_context, "-C": context_alias, "-n": line_numbers,
    }
    args = {k: v for k, v in kwargs.items() if v is not None}
    raw = _get_transport().call_tool("Grep", args)
    return _parse("Grep", raw)


# --- Execution ---

def Bash(command: str, timeout: int = None, description: str = None) -> str:
    return _call("Bash", command=command, timeout=timeout, description=description)


# --- Agent Orchestration ---

def Agent(description: str, prompt: str, subagent_type: str = None, model: str = None,
          run_in_background: bool = None, name: str = None, team_name: str = None,
          mode: str = None, isolation: str = None) -> str:
    """Spawn a sub-agent using claude-agent-sdk."""
    agents = _get_agent_definitions()

    # Resolve agent definition by subagent_type or name
    agent_def = None
    if subagent_type and subagent_type in agents:
        agent_def = agents[subagent_type]
    elif name and name in agents:
        agent_def = agents[name]

    # System prompt: agent definition prompt appended to Claude Code defaults
    system_prompt_val = None
    if agent_def and agent_def.prompt:
        system_prompt_val = {"type": "preset", "preset": "claude_code", "append": agent_def.prompt}

    # Model: explicit param > agent definition > None (SDK default)
    resolved_model = model
    if resolved_model is None and agent_def and agent_def.model and agent_def.model != "inherit":
        resolved_model = agent_def.model

    # Tools: from agent definition if available
    resolved_tools = None
    if agent_def and agent_def.tools:
        resolved_tools = agent_def.tools

    async def _run():
        result_text = ""
        opts = ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            model=resolved_model,
            agents=agents or None,
            cwd=os.getcwd(),
            system_prompt=system_prompt_val,
        )
        if resolved_tools:
            opts.allowed_tools = resolved_tools
        async for msg in query(prompt=prompt, options=opts):
            if isinstance(msg, ResultMessage):
                result_text = msg.result
        return result_text

    has_loop = True
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        has_loop = False

    if has_loop:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, _run())
            return future.result()
    else:
        return asyncio.run(_run())


def SendMessage(to: str, message: str, summary: str = None) -> str:
    return _call("SendMessage", to=to, message=message, summary=summary)


def TaskOutput(task_id: str, block: bool = None, timeout: int = None) -> str:
    return _call("TaskOutput", task_id=task_id, block=block, timeout=timeout)


def TaskStop(task_id: str = None, shell_id: str = None) -> str:
    return _call("TaskStop", task_id=task_id, shell_id=shell_id)


# --- Web ---

def WebFetch(url: str, prompt: str) -> str:
    return _call("WebFetch", url=url, prompt=prompt)


def WebSearch(query: str, allowed_domains: list = None, blocked_domains: list = None) -> str:
    return _call("WebSearch", query=query, allowed_domains=allowed_domains, blocked_domains=blocked_domains)


# --- Scheduling ---

def CronCreate(cron: str, prompt: str, recurring: bool = None, durable: bool = None) -> str:
    return _call("CronCreate", cron=cron, prompt=prompt, recurring=recurring, durable=durable)


def CronDelete(id: str) -> str:
    return _call("CronDelete", id=id)


def CronList() -> str:
    return _call("CronList")


# --- Teams ---

def TeamCreate(team_name: str, description: str = None, agent_type: str = None) -> str:
    return _call("TeamCreate", team_name=team_name, description=description, agent_type=agent_type)


def TeamDelete() -> str:
    return _call("TeamDelete")


# --- Remote ---

def RemoteTrigger(action: str, trigger_id: str = None, body: str = None) -> str:
    return _call("RemoteTrigger", action=action, trigger_id=trigger_id, body=body)


# --- Worktree ---

def EnterWorktree(name: str) -> str:
    return _call("EnterWorktree", name=name)


def ExitWorktree(action: str, discard_changes: bool = None) -> str:
    return _call("ExitWorktree", action=action, discard_changes=discard_changes)


# --- Misc ---

def Skill(skill: str, args: str = None) -> str:
    return _call("Skill", skill=skill, args=args)


def ToolSearch(query: str, max_results: int = None) -> str:
    return _call("ToolSearch", query=query, max_results=max_results)


def NotebookEdit(notebook_path: str, new_source: str, cell_id: str = None,
                 cell_type: str = None, edit_mode: str = None) -> str:
    return _call("NotebookEdit", notebook_path=notebook_path, new_source=new_source,
                 cell_id=cell_id, cell_type=cell_type, edit_mode=edit_mode)
