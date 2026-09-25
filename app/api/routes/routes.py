import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.llm.client import OllamaClient
from app.schemas.chat import (
    ApprovalDecision,
    ApprovalResult,
    ChatRequest,
    ChatResponse,
    PendingApproval,
)
from app.services.agent import FridayAgent
from app.services.approvals import ApprovalBroker

router = APIRouter(prefix="/api")

# One broker for the process. A request opened by the WebSocket transport can
# be answered over REST and vice versa; there is only ever one pending set.
broker = ApprovalBroker(settings.approval_timeout_seconds)


@router.get("/health")
def health():
    return {"status": "ok", }


@router.get("/local-status")
async def local_status():
    """Show whether the local Ollama server is reachable and the configured model is installed."""
    client = OllamaClient(settings.ollama_base_url, settings.ollama_model)
    try:
        data = await client.health()
    except Exception as exc:
        return {
            "local_only": True,
            "ollama_reachable": False,
            "model": settings.ollama_model,
            "error": str(exc),
        }

    names = {item.get("name") for item in data.get("models", [])}
    return {
        "local_only": True,
        "ollama_reachable": True,
        "model": settings.ollama_model,
        "model_installed": settings.ollama_model in names,
    }


@router.get("/approvals", response_model=list[PendingApproval])
async def list_approvals():
    """Tool calls currently waiting on a human decision."""
    return broker.pending()


@router.post("/approvals/{approval_id}", response_model=ApprovalResult)
def resolve_approval(approval_id: str, decision: ApprovalDecision):
    """Answer a pending tool call.

    `recorded` is False when the id is unknown or was already answered, which
    includes a request that has expired into a denial.
    """
    recorded = broker.resolve(approval_id, decision.approved)
    return ApprovalResult(
        id=approval_id, approved=decision.approved, recorded=recorded
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Run one turn. Holds the connection while a mutating tool awaits approval.

    Poll `GET /api/approvals` and answer `POST /api/approvals/{id}` to release
    it. Unanswered requests expire as denials after FRIDAY_APPROVAL_TIMEOUT_SECONDS.
    """

    async def approve(tool: str, arguments: dict) -> bool:
        return await broker.wait(broker.open(tool, arguments).id)

    agent = FridayAgent(approval_fn=approve)
    try:
        answer = await agent.chat(request.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(response=answer, tool_events=agent.tool_events)


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    """Interactive session: approval requests are pushed and answered in-band.

    Client sends  {"message": "..."}
    Server may send {"type": "approval_request", "id", "tool", "arguments"}
    Client replies  {"type": "approval_response", "id": "...", "approved": bool}
    Server sends    {"type": "final", "response": "...", "tool_events": [...]}

    One agent lives for the connection, so conversation memory persists across
    turns for the life of the socket.
    """
    await websocket.accept()

    inbox: asyncio.Queue = asyncio.Queue()
    disconnected = asyncio.Event()

    async def approve(tool: str, arguments: dict) -> bool:
        request = broker.open(tool, arguments)
        try:
            await websocket.send_json(
                {"type": "approval_request", **request.as_dict()}
            )
        except Exception:
            # Socket is gone; nobody can answer, so it is a denial.
            broker.resolve(request.id, False)
        return await broker.wait(request.id)

    agent = FridayAgent(approval_fn=approve)

    async def reader():
        """Sole reader of the socket: routes decisions to the broker, rest to the inbox."""
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "approval_response":
approved = data.get("approved")
                    if isinstance(approved, bool):
                        broker.resolve(str(data.get("id")), approved)
                else:
                    await inbox.put(data)
        except (WebSocketDisconnect, RuntimeError, ValueError):
            pass
        finally:
            disconnected.set()
            await inbox.put(None)

    reader_task = asyncio.create_task(reader())
    try:
        while True:
            data = await inbox.get()
            if data is None:
                break

            message = str(data.get("message") or "").strip()
            if not message:
                await websocket.send_json(
                    {"type": "error", "detail": "message must be a non-empty string"}
                )
                continue

            try:
                answer = await agent.chat(message)
            except Exception as exc:
                if disconnected.is_set():
                    break
                await websocket.send_json({"type": "error", "detail": str(exc)})
                continue

            if disconnected.is_set():
                break
            await websocket.send_json(
                {
                    "type": "final",
                    "response": answer,
                    "tool_events": agent.tool_events,
                }
            )
    finally:
        reader_task.cancel()
