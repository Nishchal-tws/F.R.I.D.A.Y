"""Approval broker.

A tool call that mutates the workspace may only run after a human says so.
This module is the single place that decision is recorded, so every transport
(CLI, WebSocket, REST polling) resolves the same pending request.

A request that is never answered expires as a denial. Silence is never consent.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field


@dataclass
class ApprovalRequest:
    id: str
    tool: str
    arguments: dict
    decision: asyncio.Future[bool] = field(repr=False)

    def as_dict(self) -> dict:
        return {"id": self.id, "tool": self.tool, "arguments": self.arguments}


class ApprovalBroker:
    """Holds approval requests that are waiting on a human."""

    def __init__(self, timeout_seconds: int):
        self.timeout_seconds = timeout_seconds
        self._pending: dict[str, ApprovalRequest] = {}

    def open(self, tool: str, arguments: dict) -> ApprovalRequest:
        """Register a request and return it so a transport can announce it."""
        request = ApprovalRequest(
            id=uuid.uuid4().hex[:12],
            tool=tool,
            arguments=arguments,
            decision=asyncio.get_running_loop().create_future(),
        )
        self._pending[request.id] = request
        return request

    async def wait(self, request_id: str) -> bool:
        """Block until the request is answered, or deny it once it times out."""
        request = self._pending.get(request_id)
        if request is None:
            return False
        try:
            return await asyncio.wait_for(
                asyncio.shield(request.decision), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            return False
        finally:
            self._pending.pop(request_id, None)

    def resolve(self, request_id: str, approved: bool) -> bool:
        """Record a decision. Returns False if there was nothing to answer."""
        request = self._pending.get(request_id)
        if request is None or request.decision.done():
            return False
        request.decision.set_result(approved)
        return True

    def pending(self) -> list[dict]:
        return [
            request.as_dict()
            for request in self._pending.values()
            if not request.decision.done()
        ]
