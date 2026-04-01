import atexit
from claude_code_orchestrate.mcp_transport import MCPTransport

_transport: MCPTransport | None = None


def _get_transport() -> MCPTransport:
    global _transport
    if _transport is None:
        _transport = MCPTransport()
        _transport.start()
        atexit.register(_transport.stop)
    return _transport


def _call(tool_name: str, **kwargs) -> str:
    args = {k: v for k, v in kwargs.items() if v is not None}
    return _get_transport().call_tool(tool_name, args)


# --- File Tools ---

def Read(file_path: str, offset: int = None, limit: int = None, pages: str = None) -> str:
    return _call("Read", file_path=file_path, offset=offset, limit=limit, pages=pages)


def Write(file_path: str, content: str) -> str:
    return _call("Write", file_path=file_path, content=content)


def Edit(file_path: str, old_string: str, new_string: str, replace_all: bool = None) -> str:
    return _call("Edit", file_path=file_path, old_string=old_string, new_string=new_string, replace_all=replace_all)


def Glob(pattern: str, path: str = None) -> str:
    return _call("Glob", pattern=pattern, path=path)


def Grep(pattern: str, path: str = None, glob: str = None, output_mode: str = None,
         type: str = None, head_limit: int = None, offset: int = None,
         multiline: bool = None, context: int = None) -> str:
    return _call("Grep", pattern=pattern, path=path, glob=glob, output_mode=output_mode,
                 type=type, head_limit=head_limit, offset=offset, multiline=multiline, context=context)


# --- Execution ---

def Bash(command: str, timeout: int = None, description: str = None) -> str:
    return _call("Bash", command=command, timeout=timeout, description=description)


# --- Agent Orchestration ---

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
