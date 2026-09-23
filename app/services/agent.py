import json
from typing import Callable, Awaitable
from app.core.config import settings
from app.llm.client import OllamaClient
from app.memory.manager import ConversationMemory
from app.tools.registry import ToolContext, TOOL_DEFINITIONS, TOOL_FUNCTIONS, ToolError

SYSTEM_PROMPT = """You are FRIDAY, a private personal engineering assistant.
The user is the developer and decision-maker.

Inspect repository context before making repository-specific claims.
Do not claim a file changed unless a tool actually changed it.
Prefer small reversible changes.
After edits, inspect git diff and run focused tests.
Clearly distinguish proposed actions from executed actions and verified results.
"""

ApprovalFn = Callable[[str], Awaitable[bool]]

class FridayAgent:
    def __init__(self, approval_fn: ApprovalFn | None = None):
        self.llm = OllamaClient(settings.ollama_base_url, settings.ollama_model)
        self.memory = ConversationMemory()
        self.context = ToolContext(settings.workspace, settings.max_file_bytes, settings.shell_timeout_seconds)
        self.approval_fn = approval_fn
        self.tool_events = []

    async def _approve(self, action: str) -> bool:
        return await self.approval_fn(action) if self.approval_fn else False

    async def chat(self, user_message: str, autonomous: bool = False) -> str:
        self.tool_events = []
        self.memory.add("user", user_message)
        messages = [{"role":"system","content":SYSTEM_PROMPT}, *self.memory.as_messages()]

        for _ in range(settings.max_tool_iterations):
            result = await self.llm.chat(messages, tools=TOOL_DEFINITIONS)
            assistant = result.get("message", {})
            messages.append(assistant)
            calls = assistant.get("tool_calls") or []
            if not calls:
                response = assistant.get("content", "").strip()
                self.memory.add("assistant", response)
                return response

            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args)

                if name not in TOOL_FUNCTIONS:
                    output = f"Unknown tool: {name}"
                else:
                    approved = autonomous or name not in {"write_file", "run_shell"}
                    if not approved:
                        approved = await self._approve(
                            f"FRIDAY requests {name}:\n{json.dumps(args, indent=2)}"
                        )
                    if not approved:
                        output = "Action denied by user."
                    else:
                        try:
                            output = TOOL_FUNCTIONS[name](self.context, **args)
                        except (ToolError, OSError, TimeoutError, ValueError) as exc:
                            output = f"Tool error: {exc}"

                self.tool_events.append({"tool": name, "arguments": args, "output": output})
                messages.append({"role":"tool","content":output})

        return "I stopped after the maximum tool iterations."
