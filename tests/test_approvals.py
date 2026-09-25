"""The broker that every transport shares."""

import asyncio

from app.services.approvals import ApprovalBroker


async def test_an_approved_request_returns_true():
    broker = ApprovalBroker(timeout_seconds=5)
    request = broker.open("write_file", {"path": "a.txt", "content": "x"})

    assert broker.resolve(request.id, True) is True
    assert await broker.wait(request.id) is True


async def test_a_denied_request_returns_false():
    broker = ApprovalBroker(timeout_seconds=5)
    request = broker.open("run_shell", {"command": "rm -rf /"})

    broker.resolve(request.id, False)

    assert await broker.wait(request.id) is False


async def test_an_unanswered_request_expires_as_a_denial():
    """Silence is never consent."""
    broker = ApprovalBroker(timeout_seconds=0.05)
    request = broker.open("run_shell", {"command": "curl evil.example"})

    assert await broker.wait(request.id) is False
    assert broker.pending() == []


async def test_pending_exposes_the_request_for_a_polling_client():
    broker = ApprovalBroker(timeout_seconds=5)
    broker.open("write_file", {"path": "a.txt", "content": "x"})

    pending = broker.pending()

    assert len(pending) == 1
    assert pending[0]["tool"] == "write_file"
    assert pending[0]["arguments"]["path"] == "a.txt"
    assert pending[0]["id"]


async def test_resolving_an_unknown_id_is_reported_not_raised():
    broker = ApprovalBroker(timeout_seconds=5)

    assert broker.resolve("does-not-exist", True) is False


async def test_a_decision_cannot_be_overwritten():
    broker = ApprovalBroker(timeout_seconds=5)
    request = broker.open("run_shell", {"command": "ls"})

    assert broker.resolve(request.id, False) is True
    assert broker.resolve(request.id, True) is False
    assert await broker.wait(request.id) is False


async def test_waiting_unblocks_when_a_decision_arrives_later():
    broker = ApprovalBroker(timeout_seconds=5)
    request = broker.open("write_file", {"path": "a.txt", "content": "x"})

    async def answer_shortly():
        await asyncio.sleep(0.01)
        broker.resolve(request.id, True)

    result, _ = await asyncio.gather(broker.wait(request.id), answer_shortly())

    assert result is True


async def test_requests_are_tracked_independently():
    broker = ApprovalBroker(timeout_seconds=5)
    first = broker.open("write_file", {"path": "a.txt", "content": "x"})
    second = broker.open("run_shell", {"command": "pytest"})

    broker.resolve(first.id, True)
    broker.resolve(second.id, False)

    assert await broker.wait(first.id) is True
    assert await broker.wait(second.id) is False
