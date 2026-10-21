"""The local-only guarantee is the project's headline privacy claim.

These tests hold the line described in docs/LOCAL_AI.md.
"""

import pytest

from app.core.config import settings, validate_local_only_configuration
from app.llm.client import OllamaClient


@pytest.mark.parametrize(
    "base_url",
    ["http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434"],
)
def test_loopback_endpoints_are_accepted(monkeypatch, base_url):
    monkeypatch.setattr(settings, "ollama_base_url", base_url)
    validate_local_only_configuration()


@pytest.mark.parametrize(
    "base_url",
    [
        "http://10.0.0.5:11434",
        "https://api.example.com",
        "http://ollama.internal:11434",
        "http://127.0.0.1.evil.com:11434",
    ],
)
def test_remote_endpoints_are_rejected(monkeypatch, base_url):
    monkeypatch.setattr(settings, "ollama_base_url", base_url)
    with pytest.raises(RuntimeError, match="local-only"):
        validate_local_only_configuration()


@pytest.mark.parametrize("model", ["gpt-oss:120b-cloud", "qwen3-coder:480b-cloud"])
def test_cloud_model_names_are_rejected(monkeypatch, model):
    monkeypatch.setattr(settings, "ollama_model", model)
    with pytest.raises(RuntimeError, match="local-only"):
        validate_local_only_configuration()


def test_client_refuses_to_construct_against_a_remote_endpoint(monkeypatch):
    """The guard runs in OllamaClient.__init__, so a remote client cannot exist."""
    monkeypatch.setattr(settings, "ollama_base_url", "https://api.example.com")
    with pytest.raises(RuntimeError, match="local-only"):
        OllamaClient("https://api.example.com", "qwen2.5-coder:7b")
