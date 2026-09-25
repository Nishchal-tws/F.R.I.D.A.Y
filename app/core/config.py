from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FRIDAY"
    workspace: Path
    ollama_base_url: str 
    ollama_model: str 
    max_file_bytes: int 
    shell_timeout_seconds: int 
    max_tool_iterations: int 

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FRIDAY_",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
settings.workspace = settings.workspace.resolve()


def validate_local_only_configuration() -> None:
    """Fail fast if FRIDAY is configured to use a remote endpoint/model."""
    allowed_hosts = {"127.0.0.1", "localhost", "::1"}
    from urllib.parse import urlparse

    parsed = urlparse(settings.ollama_base_url)
    host = (parsed.hostname or "").lower()
    if host not in allowed_hosts:
        raise RuntimeError(
            "FRIDAY is local-only. FRIDAY_OLLAMA_BASE_URL must point to localhost. "
            f"Got: {settings.ollama_base_url}"
        )

    model = settings.ollama_model.lower()
    if "-cloud" in model or model.endswith("cloud"):
        raise RuntimeError(
            "FRIDAY is local-only. Cloud Ollama model names are not allowed: "
            f"{settings.ollama_model}"
        )
