from fastapi import APIRouter, HTTPException

from app.services.agent import FridayAgent
from app.core.config import settings
from app.llm.client import OllamaClient
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api")


async def no_auto_approval(_: str) -> bool:
    return False


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


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    agent = FridayAgent(approval_fn=no_auto_approval)
    try:
        answer = await agent.chat(request.message, autonomous=request.autonomous)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(response=answer, tool_events=agent.tool_events)
