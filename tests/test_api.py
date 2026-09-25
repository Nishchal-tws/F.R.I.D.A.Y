"""The ASGI surface, including both approval transports end to end."""

import asyncio

import pytest
from conftest import final_message, tool_call_message
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.api.routes import routes
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
async def async_client():
    """A client that can hold one request open while another answers it."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://friday.test"
    ) as ac:
        yield ac


def test_root_reports_the_service(client):
    assert client.get("/").json()["name"] == "FRIDAY"


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_local_status_reports_an_unreachable_ollama(client, monkeypatch):
    async def unreachable(self):
        raise ConnectionError("All connection attempts failed")

    monkeypatch.setattr(routes.OllamaClient, "health", unreachable)

    body = client.get("/api/local-status").json()

    assert body["local_only"] is True
    assert body["ollama_reachable"] is False


def test_chat_rejects_an_autonomous_flag(client):
    """Regression: `{"autonomous": true}` used to bypass the approval gate."""
    response = client.post(
        "/api/chat", json={"message": "rm -rf /", "autonomous": True}
    )

    assert response.status_code == 422


def test_chat_rejects_an_empty_message(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


def test_chat_returns_a_read_only_turn(client, scripted_llm, workspace):
    scripted_llm([tool_call_message("git_status"), final_message("Clean.")])

    body = client.post("/api/chat", json={"message": "status?"}).json()

    assert body["response"] == "Clean."
    assert body["tool_events"][0]["tool"] == "git_status"


def test_approvals_list_is_empty_when_nothing_waits(client):
    assert client.get("/api/approvals").json() == []


def test_answering_an_unknown_approval_is_not_recorded(client):
    body = client.post("/api/approvals/nope", json={"approved": True}).json()

    assert body["recorded"] is False


async def _wait_for_pending(ac):
    """Poll the approvals endpoint until the held chat registers its request."""
    for _ in range(200):
        pending = (await ac.get("/api/approvals")).json()
        if pending:
            return pending[0]
        await asyncio.sleep(0.01)
    raise AssertionError("no approval request appeared")


async def test_rest_polling_approval_releases_a_held_write(
    async_client, scripted_llm, workspace
):
    scripted_llm(
        [
            tool_call_message("write_file", path="approved.txt", content="yes"),
            final_message("Wrote approved.txt."),
        ]
    )
    turn = asyncio.create_task(
        async_client.post("/api/chat", json={"message": "write it"})
    )

    pending = await _wait_for_pending(async_client)
    assert pending["tool"] == "write_file"
    await async_client.post(f"/api/approvals/{pending['id']}", json={"approved": True})

    body = (await turn).json()

    assert body["response"] == "Wrote approved.txt."
    assert (workspace / "approved.txt").read_text() == "yes"


async def test_rest_polling_denial_blocks_the_write(
    async_client, scripted_llm, workspace
):
    scripted_llm(
        [
            tool_call_message("write_file", path="denied.txt", content="no"),
            final_message("The write was denied."),
        ]
    )
    turn = asyncio.create_task(
        async_client.post("/api/chat", json={"message": "write it"})
    )

    pending = await _wait_for_pending(async_client)
    await async_client.post(f"/api/approvals/{pending['id']}", json={"approved": False})

    body = (await turn).json()

    assert not (workspace / "denied.txt").exists()
    assert "denied" in body["tool_events"][0]["output"].lower()


async def test_an_ignored_approval_expires_and_denies_the_write(
    async_client, scripted_llm, workspace
):
    """Nobody answers, so the held turn finishes as a denial rather than hanging."""
    scripted_llm(
        [
            tool_call_message("write_file", path="ignored.txt", content="no"),
            final_message("Timed out waiting for approval."),
        ]
    )

    body = (await async_client.post("/api/chat", json={"message": "write it"})).json()

    assert not (workspace / "ignored.txt").exists()
    assert "denied" in body["tool_events"][0]["output"].lower()


def test_websocket_approval_writes_the_file(client, scripted_llm, workspace):
    scripted_llm(
        [
            tool_call_message("write_file", path="ws.txt", content="via socket"),
            final_message("Wrote ws.txt."),
        ]
    )

    with client.websocket_connect("/api/ws/chat") as ws:
        ws.send_json({"message": "write it"})

        request = ws.receive_json()
        assert request["type"] == "approval_request"
        assert request["tool"] == "write_file"
        assert request["arguments"] == {"path": "ws.txt", "content": "via socket"}

        ws.send_json(
            {"type": "approval_response", "id": request["id"], "approved": True}
        )
        result = ws.receive_json()

    assert result["type"] == "final"
    assert result["response"] == "Wrote ws.txt."
    assert (workspace / "ws.txt").read_text() == "via socket"


def test_websocket_denial_blocks_the_file(client, scripted_llm, workspace):
    scripted_llm(
        [
            tool_call_message("write_file", path="ws-denied.txt", content="no"),
            final_message("Denied."),
        ]
    )

    with client.websocket_connect("/api/ws/chat") as ws:
        ws.send_json({"message": "write it"})
        request = ws.receive_json()
        ws.send_json(
            {"type": "approval_response", "id": request["id"], "approved": False}
        )
        result = ws.receive_json()

    assert not (workspace / "ws-denied.txt").exists()
    assert "denied" in result["tool_events"][0]["output"].lower()


def test_websocket_read_only_turn_needs_no_approval(client, scripted_llm, workspace):
    scripted_llm([tool_call_message("git_status"), final_message("Clean.")])

    with client.websocket_connect("/api/ws/chat") as ws:
        ws.send_json({"message": "status?"})
        result = ws.receive_json()

    assert result["type"] == "final"
    assert result["response"] == "Clean."


def test_websocket_rejects_an_empty_message(client, scripted_llm, workspace):
    scripted_llm([final_message("unused")])

    with client.websocket_connect("/api/ws/chat") as ws:
        ws.send_json({"message": "   "})
        result = ws.receive_json()

    assert result["type"] == "error"


def test_websocket_keeps_memory_across_turns(client, scripted_llm, workspace):
    """One agent lives for the connection, unlike the stateless REST path."""
    llm = scripted_llm([final_message("first"), final_message("second")])

    with client.websocket_connect("/api/ws/chat") as ws:
        ws.send_json({"message": "one"})
        ws.receive_json()
        ws.send_json({"message": "two"})
        ws.receive_json()

    roles = [message["role"] for message in llm.calls[-1]]
    assert roles.count("user") == 2
