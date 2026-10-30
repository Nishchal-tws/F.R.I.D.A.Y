from __future__ import annotations

import httpx

from app.core.config import ModelSettings


class OllamaClient:
    """Local-only Ollama client. No cloud fallback is implemented."""

    def __init__(self, settings: ModelSettings):
        self.settings = settings

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{self.settings.ollama_base_url}/api/tags")
            response.raise_for_status()
            return response.json()

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        
        payload = {
            "model": self.settings.ollama_model,
            "messages": messages,
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "temperature": self.settings.temperature,
                "num_ctx": self.settings.num_ctx,
                "top_p": self.settings.top_p,
                "top_k": self.settings.top_k,
                "min_p": self.settings.min_p,
                "num_predict": self.settings.num_predict,
                "repeat_penalty": self.settings.repeat_penalty,
                "repeat_last_n": self.settings.repeat_last_n,
                "seed": self.settings.seed,
                "stop": self.settings.stop
            }
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{self.settings.ollama_base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
