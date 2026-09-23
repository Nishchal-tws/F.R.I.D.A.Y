from __future__ import annotations
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ToolContext:
    workspace: Path
    max_file_bytes: int
    shell_timeout_seconds: int

class ToolError(RuntimeError):
    pass

def _safe_path(ctx: ToolContext, relative_path: str) -> Path:
    candidate = (ctx.workspace / relative_path).resolve()
    try:
        candidate.relative_to(ctx.workspace)
    except ValueError as exc:
        raise ToolError("Path escapes the configured FRIDAY workspace.") from exc
    return candidate

def list_files(ctx: ToolContext, path: str = ".") -> str:
    target = _safe_path(ctx, path)
    if not target.is_dir():
        raise ToolError(f"Not a directory: {path}")
    ignored = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}
    rows = []
    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if item.name in ignored:
            continue
        rows.append(f"{'[DIR]' if item.is_dir() else '[FILE]'} {item.relative_to(ctx.workspace)}")
    return "\n".join(rows[:500]) or "(empty)"

def read_file(ctx: ToolContext, path: str) -> str:
    target = _safe_path(ctx, path)
    if not target.is_file():
        raise ToolError(f"File does not exist: {path}")
    if target.stat().st_size > ctx.max_file_bytes:
        raise ToolError("File exceeds configured size limit.")
    return target.read_text(encoding="utf-8", errors="replace")

def search_code(ctx: ToolContext, query: str) -> str:
    ignored = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}
    matches = []
    needle = query.lower()
    for path in ctx.workspace.rglob("*"):
        if not path.is_file() or any(p in ignored for p in path.parts):
            continue
        try:
            if path.stat().st_size > ctx.max_file_bytes:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if needle in line.lower():
                matches.append(f"{path.relative_to(ctx.workspace)}:{n}: {line[:300]}")
                if len(matches) >= 200:
                    return "\n".join(matches)
    return "\n".join(matches) or "(no matches)"

def git_status(ctx: ToolContext) -> str:
    r = subprocess.run(["git", "status", "--short", "--branch"], cwd=ctx.workspace,
                       capture_output=True, text=True, timeout=ctx.shell_timeout_seconds)
    return (r.stdout + r.stderr).strip() or "(clean)"

def git_diff(ctx: ToolContext) -> str:
    r = subprocess.run(["git", "diff", "--", "."], cwd=ctx.workspace,
                       capture_output=True, text=True, timeout=ctx.shell_timeout_seconds)
    return r.stdout[-20000:] or "(no diff)"

def write_file(ctx: ToolContext, path: str, content: str) -> str:
    target = _safe_path(ctx, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {target.relative_to(ctx.workspace)}"

def run_shell(ctx: ToolContext, command: str) -> str:
    r = subprocess.run(command, cwd=ctx.workspace, shell=True,
                       capture_output=True, text=True,
                       timeout=ctx.shell_timeout_seconds, env=os.environ.copy())
    output = (r.stdout + "\n" + r.stderr).strip()
    return f"exit_code={r.returncode}\n{output[-20000:]}"

TOOL_DEFINITIONS = [
    {"type":"function","function":{"name":"list_files","description":"List files and directories inside the workspace.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"read_file","description":"Read a source/config file inside the workspace.","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"search_code","description":"Search source code for text inside the workspace.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"git_status","description":"Get git branch and working tree status.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"git_diff","description":"Get current git diff.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"write_file","description":"Write or replace a file inside the workspace.","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"run_shell","description":"Run a development command in the workspace.","parameters":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}},
]

TOOL_FUNCTIONS = {
    "list_files": list_files,
    "read_file": read_file,
    "search_code": search_code,
    "git_status": git_status,
    "git_diff": git_diff,
    "write_file": write_file,
    "run_shell": run_shell,
}
