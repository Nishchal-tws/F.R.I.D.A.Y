"""Test configuration.

`app.core.config` builds its settings singleton at import time and requires
FRIDAY_WORKSPACE, so the environment is pinned here before anything imports the
package. Explicit env vars also win over a developer's local `.env`, which keeps
CI and a working machine on identical settings.
"""

import os
import subprocess
import tempfile
from pathlib import Path

_WORKSPACE = Path(tempfile.mkdtemp(prefix="friday-test-workspace-"))

os.environ["FRIDAY_WORKSPACE"] = str(_WORKSPACE)
os.environ["FRIDAY_OLLAMA_BASE_URL"] = "http://127.0.0.1:11434"
os.environ["FRIDAY_OLLAMA_MODEL"] = "test-model"
os.environ["FRIDAY_APPROVAL_TIMEOUT_SECONDS"] = "2"
os.environ["FRIDAY_MAX_TOOL_ITERATIONS"] = "6"

import pytest  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.tools.registry import ToolContext  # noqa: E402


class FakeLLM:
    """Stands in for OllamaClient so tests never need a running model."""

    def __init__(self, responses=None, model="test-model"):
        self.base_url = "http://127.0.0.1:11434"
        self.model = model
        self.responses = list(responses or [])
        self.calls = []

    async def chat(self, messages, tools=None):
        self.calls.append(messages)
        if not self.responses:
            return final_message("(script exhausted)")
        return self.responses.pop(0)

    async def health(self):
        return {"models": [{"name": self.model}]}


def tool_call_message(name, **arguments):
    """An assistant turn that asks for one tool call."""
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
        }
    }


def final_message(text):
    """An assistant turn with no tool calls, which ends the agent loop."""
    return {"message": {"role": "assistant", "content": text}}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """An isolated workspace that both ToolContext and the settings point at."""
    monkeypatch.setattr(settings, "workspace", tmp_path)
    return tmp_path


@pytest.fixture
def context(workspace):
    return ToolContext(
        workspace=workspace, max_file_bytes=1000, shell_timeout_seconds=10
    )


@pytest.fixture
def git_workspace(workspace):
    """A workspace that is a git repo with one committed file."""
    identity = [
        "-c", "user.email=tests@example.invalid",
        "-c", "user.name=FRIDAY tests",
        "-c", "commit.gpgsign=false",
    ]
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=workspace, check=True)
    (workspace / "tracked.txt").write_text("original\n", encoding="utf-8")
    subprocess.run([*identity[:0], "git", "add", "-A"], cwd=workspace, check=True)
    subprocess.run(
        ["git", *identity, "commit", "-qm", "initial"], cwd=workspace, check=True
    )
    return workspace


@pytest.fixture
def scripted_llm(monkeypatch):
    """Install a FakeLLM in place of the agent's OllamaClient.

    Returns a factory so each test scripts its own model turns.
    """

    def install(responses):
        fake = FakeLLM(responses=responses)
        monkeypatch.setattr(
            "app.services.agent.OllamaClient", lambda base_url, model: fake
        )
        return fake

    return install
