import json
from typing import Awaitable, Callable

from app.core.config import settings
from app.llm.client import OllamaClient
from app.memory.manager import ConversationMemory
from app.tools.registry import TOOL_DEFINITIONS, TOOL_FUNCTIONS, ToolContext, ToolError

SYSTEM_PROMPT = """You are FRIDAY, a private personal engineering assistant.
The user is the developer and decision-maker.

Inspect repository context before making repository-specific claims.
Do not claim a file changed unless a tool actually changed it.
Prefer small reversible changes.
After edits, inspect git diff and run focused tests.
Clearly distinguish proposed actions from executed actions and verified results.
"""

# Tools that change the machine. These never run without a human decision.
# There is no caller-supplied flag that skips this set.
REQUIRES_APPROVAL = frozenset({"write_file", "run_shell"})

ApprovalFn = Callable[[str, dict], Awaitable[bool]]


class FridayAgent:
    def __init__(self, approval_fn: ApprovalFn | None = None):
        self.llm = OllamaClient(settings.ollama_base_url, settings.ollama_model)
        self.memory = ConversationMemory()
        self.context = ToolContext(
            settings.workspace, settings.max_file_bytes, settings.shell_timeout_seconds
        )
        self.approval_fn = approval_fn
        self.tool_events = []

    async def _approve(self, tool: str, arguments: dict) -> bool:
        """A mutating tool runs only if a human approves it.

        With no approval channel there is nobody to ask, so the answer is no.
        """
        if self.approval_fn is None:
            return False
        return await self.approval_fn(tool, arguments)

    async def _run_tool(self, name: str, arguments: dict) -> str:
        if name not in TOOL_FUNCTIONS:
            return f"Unknown tool: {name}"

        if name in REQUIRES_APPROVAL and not await self._approve(name, arguments):
            return "Action denied: the user did not approve this tool call."

        try:
            return TOOL_FUNCTIONS[name](self.context, **arguments)
        except (ToolError, OSError, TimeoutError, ValueError, TypeError) as exc:
            return f"Tool error: {exc}"

    async def chat(self, user_message: str) -> str:
        self.tool_events = []
        self.memory.add("user", user_message)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.memory.as_messages(),
        ]

        for _ in range(settings.max_tool_iterations):
            result = await self.llm.chat(messages, tools=TOOL_DEFINITIONS)
            assistant = result.get("message", {})
            messages.append(assistant)
            calls = assistant.get("tool_calls") or []
            if not calls:
                response = (assistant.get("content") or "").strip()
                self.memory.add("assistant", response)
                return response

            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name")
                arguments = fn.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                output = await self._run_tool(name, arguments)
                self.tool_events.append(
                    {"tool": name, "arguments": arguments, "output": output}
                )
                messages.append({"role": "tool", "content": output})

        return "I stopped after the maximum tool iterations."
