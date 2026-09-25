import json
import re
from typing import Callable, Awaitable
from app.core.config import settings
from app.llm.client import OllamaClient
from app.memory.manager import ConversationMemory
from app.tools.registry import ToolContext, TOOL_DEFINITIONS, TOOL_FUNCTIONS, ToolError

SYSTEM_PROMPT = """You are FRIDAY, a private personal engineering assistant.
The user is the developer and decision-maker.
For a greeting, respond naturally and start with "Hello Sir".
Answer general questions conversationally. Use a tool only when the request requires information or an action from that tool.
When a tool is needed, call it using the provided function calling interface. Never print tool-call JSON as your answer.
Use git_status only when the user asks about Git or repository status, the current branch, or the working tree.
Inspect repository context before making repository-specific claims; use relevant tools such as list_files or read_file rather than git_status for project identity.
Ask for approval before actions that modify files or run shell commands.
Do not claim a file changed unless a tool actually changed it.
Prefer small reversible changes.
After edits, inspect git diff and run focused tests.
Clearly distinguish proposed actions from executed actions and verified results.
"""

ApprovalFn = Callable[[str], Awaitable[bool]]


def _is_standalone_greeting(message: str) -> bool:
    normalized = re.sub(r"[^a-z ]", " ", message.lower())
    normalized = " ".join(normalized.split())
    normalized = re.sub(r"\s+friday$", "", normalized)
    return normalized in {
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
        "wake up", "daddys home", "hey dude", "hey bro", "hey buddy", "hey pal",
        "hey friend", "hey mate", "hey champ", "hey chief", "hey boss", "hey captain",
        "hey partner", "hey man", "hey buddy boy", "hey amigo", "hey compadre",
        "hey homeboy", "hey homie", "hey broseph", "hey broham", "hey brosephine",
    }


def _text_tool_call(content: str) -> dict | None:
    """Parse JSON tool-call text returned by some local models."""
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    function = payload.get("function", payload)
    if not isinstance(function, dict):
        return None
    name = function.get("name")
    arguments = function.get("arguments", {})
    if not isinstance(name, str) or not isinstance(arguments, (dict, str)):
        return None
    return {"function": {"name": name, "arguments": arguments}}


def _status_was_requested(message: str) -> bool:
    return bool(re.search(
        r"\b(git\s+status|repo(?:sitory)?\s+status|working\s+tree|current\s+branch|status)\b",
        message,
        re.IGNORECASE,
    ))


def _wants_file_contents(message: str) -> bool:
    asks_to_read = re.search(r"\b(read|open|inspect|show|access|contents?)\b", message, re.IGNORECASE)
    asks_about_content = re.search(
        r"\b(what|explain|describe|summari[sz]e|tell me|mean|saying|says|contain|contains)\b",
        message,
        re.IGNORECASE,
    )
    refers_to_file = re.search(r"\b(this|that|the)\s+(file|code)\b", message, re.IGNORECASE)
    return bool(refers_to_file and (asks_to_read or asks_about_content))


def _mentioned_file(messages: list[dict]) -> str | None:
    path_pattern = re.compile(r"(?<![\w])(?:[\w.-]+[\\/])+[\w.-]+\.[A-Za-z0-9]{1,8}")
    for message in reversed(messages):
        content = message.get("content", "")
        if not isinstance(content, str):
            continue
        matches = path_pattern.findall(content)
        if matches:
            return matches[-1].replace("\\", "/")
    return None

class FridayAgent:
    '''@Author: Nischal 
    @since: 23 Sept 2026
    '''
    def __init__(self, approval_fn: ApprovalFn | None = None):
        self.llm = OllamaClient(settings.ollama_base_url, settings.ollama_model)
        self.memory = ConversationMemory()
        self.context = ToolContext(settings.workspace, settings.max_file_bytes, settings.shell_timeout_seconds)
        self.approval_fn = approval_fn
        self.tool_events = []

    async def _approve(self, action: str) -> bool:
        return await self.approval_fn(action) if self.approval_fn else False

    async def extract_tool_call(self, user_message: str) -> dict | None :
        messages =[{"role":"system", "content":SYSTEM_PROMPT}]
        messages.extend(self.memory.as_messages())
        messages.append({"role":"user", "content":user_message})
        result = await self.llm.chat(messages, tools=TOOL_DEFINITIONS)
        assistant = result.get("message", {})
        calls = assistant.get("tool_calls") or []
        if not calls:
            return None
        return calls


    async def chat(self, user_message: str, autonomous: bool = False) -> str:
        self.tool_events = []
        self.memory.add("user", user_message)

        if _is_standalone_greeting(user_message):
            response = "Hello Sir! I’m FRIDAY, ready to help. What would you like to work on?"
            self.memory.add("assistant", response)
            return response

        messages = [{"role":"system","content":SYSTEM_PROMPT}, *self.memory.as_messages()]


        if _wants_file_contents(user_message):
            path = _mentioned_file(self.memory.as_messages())
            if path:
                args = {"path": path}
                try:
                    output = TOOL_FUNCTIONS["read_file"](self.context, **args)
                except (ToolError, OSError, TimeoutError, ValueError) as exc:
                    output = f"Tool error: {exc}"
                self.tool_events.append({"tool": "read_file", "arguments": args, "output": output})
                followup = [
                    *messages,
                    {"role": "assistant", "tool_calls": [{"function": {"name": "read_file", "arguments": args}}]},
                    {"role": "tool", "content": output},
                    {"role": "system", "content": "Answer the user's question using the file content just read. Confirm access plainly; do not ask the user to paste a file you have read."},
                ]
                result = await self.llm.chat(followup, tools=None)
                response = result.get("message", {}).get("content", "").strip()
                self.memory.add("assistant", response)
                return response

        for _ in range(settings.max_tool_iterations):
            result = await self.llm.chat(messages, tools=TOOL_DEFINITIONS)
            assistant = result.get("message", {})
            calls = assistant.get("tool_calls") or []
            if not calls:
                text_call = _text_tool_call(assistant.get("content", ""))
                if text_call and (
                    text_call["function"]["name"] != "git_status"
                    or _status_was_requested(user_message)
                ):
                    calls = [text_call]
                    messages.append({"role": "assistant", "tool_calls": calls})
                elif text_call:
                    # Do not expose a misrouted status call as JSON; ask for a plain answer.
                    fallback = await self.llm.chat(
                        [*messages, {
                            "role": "system",
                            "content": "The user did not ask for Git status. Answer their request directly and do not call tools.",
                        }],
                        tools=None,
                    )
                    response = fallback.get("message", {}).get("content", "").strip()
                    self.memory.add("assistant", response)
                    return response
                else:
                    messages.append(assistant)
            else:
                messages.append(assistant)
            if not calls:
                response = assistant.get("content", "").strip()
                self.memory.add("assistant", response)
                return response


            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                if name == "git_status" and not _status_was_requested(user_message):
                    fallback = await self.llm.chat(
                        [*messages[:-1], {
                            "role": "system",
                            "content": "The user did not ask for Git status. Answer their request directly and do not call tools.",
                        }],
                        tools=None,
                    )
                    response = fallback.get("message", {}).get("content", "").strip()
                    self.memory.add("assistant", response)
                    return response

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
