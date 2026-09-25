"""The approval gate.

The rule these tests defend: a mutating tool runs only after a human says yes,
and no caller-supplied value can substitute for that yes.
"""

import inspect

import pytest
from conftest import final_message, tool_call_message

from app.services.agent import REQUIRES_APPROVAL, FridayAgent


def approver(decision, log=None):
    """An approval_fn that always answers `decision` and records what it saw."""

    async def approve(tool, arguments):
        if log is not None:
            log.append((tool, arguments))
        return decision

    return approve


def test_the_mutating_tools_are_the_gated_ones():
    assert REQUIRES_APPROVAL == {"write_file", "run_shell"}


def test_chat_takes_no_caller_supplied_autonomy_flag():
    """Regression: `autonomous` once let a request body skip the gate."""
    parameters = inspect.signature(FridayAgent.chat).parameters

    assert set(parameters) == {"self", "user_message"}


async def test_a_denied_write_does_not_touch_the_disk(scripted_llm, workspace):
    scripted_llm(
        [
            tool_call_message("write_file", path="owned.txt", content="pwned"),
            final_message("I could not write the file."),
        ]
    )
    agent = FridayAgent(approval_fn=approver(False))

    await agent.chat("write a file")

    assert not (workspace / "owned.txt").exists()
    assert "denied" in agent.tool_events[0]["output"].lower()


async def test_an_approved_write_reaches_the_disk(scripted_llm, workspace):
    scripted_llm(
        [
            tool_call_message("write_file", path="notes.txt", content="hello"),
            final_message("Wrote notes.txt."),
        ]
    )
    agent = FridayAgent(approval_fn=approver(True))

    answer = await agent.chat("write a file")

    assert (workspace / "notes.txt").read_text() == "hello"
    assert answer == "Wrote notes.txt."


async def test_a_denied_shell_command_never_runs(scripted_llm, workspace):
    scripted_llm(
        [
            tool_call_message("run_shell", command="touch breached.txt"),
            final_message("Command denied."),
        ]
    )
    agent = FridayAgent(approval_fn=approver(False))

    await agent.chat("run a command")

    assert not (workspace / "breached.txt").exists()


async def test_no_approval_channel_means_denied(scripted_llm, workspace):
    """With nobody to ask, the answer is no rather than yes."""
    scripted_llm(
        [
            tool_call_message("run_shell", command="touch breached.txt"),
            final_message("Denied."),
        ]
    )
    agent = FridayAgent(approval_fn=None)

    await agent.chat("run a command")

    assert not (workspace / "breached.txt").exists()
    assert "denied" in agent.tool_events[0]["output"].lower()


async def test_the_approver_sees_the_tool_and_its_arguments(scripted_llm, workspace):
    """An operator cannot judge a request they cannot see."""
    seen = []
    scripted_llm(
        [
            tool_call_message("run_shell", command="rm -rf ."),
            final_message("Denied."),
        ]
    )
    agent = FridayAgent(approval_fn=approver(False, log=seen))

    await agent.chat("clean up")

    assert seen == [("run_shell", {"command": "rm -rf ."})]


@pytest.mark.parametrize("tool,arguments", [("list_files", {"path": "."}), ("git_status", {})])
async def test_read_only_tools_do_not_prompt(scripted_llm, workspace, tool, arguments):
    seen = []
    scripted_llm([tool_call_message(tool, **arguments), final_message("Listed.")])
    agent = FridayAgent(approval_fn=approver(False, log=seen))

    await agent.chat("look around")

    assert seen == [], f"{tool} should not require approval"


async def test_string_encoded_arguments_are_decoded(scripted_llm, workspace):
    """Some models emit `arguments` as a JSON string rather than an object."""
    scripted_llm(
        [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "write_file",
                                "arguments": '{"path": "s.txt", "content": "ok"}',
                            }
                        }
                    ],
                }
            },
            final_message("Wrote s.txt."),
        ]
    )
    agent = FridayAgent(approval_fn=approver(True))

    await agent.chat("write a file")

    assert (workspace / "s.txt").read_text() == "ok"


async def test_an_unknown_tool_is_reported_to_the_model(scripted_llm, workspace):
    scripted_llm(
        [
            tool_call_message("exfiltrate", target="example.com"),
            final_message("That tool does not exist."),
        ]
    )
    agent = FridayAgent(approval_fn=approver(True))

    await agent.chat("do something")

    assert "Unknown tool" in agent.tool_events[0]["output"]


async def test_a_tool_error_is_reported_instead_of_crashing(scripted_llm, workspace):
    scripted_llm(
        [
            tool_call_message("read_file", path="../../etc/passwd"),
            final_message("I cannot read outside the workspace."),
        ]
    )
    agent = FridayAgent(approval_fn=approver(True))

    answer = await agent.chat("read a file")

    assert "Tool error" in agent.tool_events[0]["output"]
    assert answer == "I cannot read outside the workspace."


async def test_the_loop_stops_at_the_iteration_ceiling(scripted_llm, workspace):
    """A model that only ever calls tools must not spin forever."""
    scripted_llm([tool_call_message("git_status") for _ in range(50)])
    agent = FridayAgent(approval_fn=approver(True))

    answer = await agent.chat("loop")

    assert "maximum tool iterations" in answer


async def test_memory_carries_across_turns(scripted_llm, workspace):
    llm = scripted_llm([final_message("first"), final_message("second")])

    await agent_chat_twice(FridayAgent(approval_fn=approver(True)))

    roles = [message["role"] for message in llm.calls[-1]]
    assert roles.count("user") == 2


async def agent_chat_twice(agent):
    await agent.chat("one")
    await agent.chat("two")
