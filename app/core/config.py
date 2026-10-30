from pathlib import Path
from typing import Tuple, Type
from dotenv import load_dotenv
import os
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource, JsonConfigSettingsSource

model_config_path = os.getenv('MODEL_CONFIG_PATH')


class ModelSettings(BaseSettings):
    app_name: str = "FRIDAY"
    workspace: Path
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    max_file_bytes: int = 200_000
    shell_timeout_seconds: int = 120
    max_tool_iterations: int = 10
    approval_timeout_seconds: int = 120
    
    # Samplers
    temperature: float = 0.7
    num_ctx: int = 2048
    top_p: float = 0.9
    top_k: int = 40
    min_p: float = 0.0
    
    # penalties and Limits
    num_predict: int = -1
    repeat_penalty: float = 1.1
    repeat_last_n: int = 64
    stop: list[str] = []
    seed: int = 0

    model_config = SettingsConfigDict(
      json_file=model_config_path, json_file_encoding="utf-8"
  )
    
        # 2. Expand the customization method
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        
        # 3. Instantiate the JSON file loader engine
        json_file_source = JsonConfigSettingsSource(settings_cls)
        
        # 4. Return the priority order (Highest priority first)
        return (
            init_settings,     # 1st priority: Explicit values passed when calling ModelSettings(temperature=0.9),
            json_file_source,  # 2nd priority: The config.json file on your disk
            env_settings,      # 3rd priority: OS Environment variables (e.g. export OLLAMA_MODEL="llama3")
            dotenv_settings,   # 4th priority: A .env file if present
        )

model_settings = ModelSettings()
model_settings.workspace = model_settings.workspace.resolve()


def validate_local_only_configuration() -> None:
    """Fail fast if FRIDAY is configured to use a remote endpoint/model."""
    allowed_hosts = {"127.0.0.1", "localhost", "::1"}
    from urllib.parse import urlparse

    parsed = urlparse(model_settings.ollama_base_url)
    host = (parsed.hostname or "").lower()
    if host not in allowed_hosts:
        raise RuntimeError(
            "FRIDAY is local-only. FRIDAY_OLLAMA_BASE_URL must point to localhost. "
            f"Got: {model_settings.ollama_base_url}"
        )

    model = model_settings.ollama_model.lower()
    if "-cloud" in model or model.endswith("cloud"):
        raise RuntimeError(
            "FRIDAY is local-only. Cloud Ollama model names are not allowed: "
            f"{model_settings.ollama_model}"
        )
