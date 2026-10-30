from pathlib import Path
import json
import logging
import os

from app.core.config import ModelSettings
from app.llm.client import OllamaClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

model_config_path = os.getenv('MODEL_CONFIG_PATH')
class ModelStateManager:
    
    def __init__(self, config_path: Path):
        
        self.config_path = config_path
        self.config = self.load_config()
        self.client = self.init_client()
        # self.memory = 
        
    def load_config(self) -> ModelSettings:
        
        try:
            with open(self.config_path, "r") as f:
                config = ModelSettings(**json.load(f))
            
            logging.info(f'Model {config.ollama_model} is loaded successfully')
            return config
        
        except FileNotFoundError:
            logging.error(f"The file was not found!")
        
        except json.JSONDecodeError:
            logging.error(f"The file {self.config_path} was corrupted or is not valid JSON")
        
        except Exception as e:
            logging.error(f"An unexpected error occurred {e}")
        
        default_config = ModelSettings()
        logging.info(f"using default model config which is {default_config.ollama_model} with temperature {default_config.temperature} and Model context length {default_config.num_ctx}")
        return default_config
    
    def init_client(self) -> OllamaClient:
        
        return OllamaClient(self.config)
    
    def update_client_params(self, **kwargs) -> ModelSettings:

        # Only catches typos / non-existent fields — partial updates are fine
        unknown = set(kwargs) - set(ModelSettings.model_fields)
        if unknown:
            raise ValueError(f"Unknown model settings: {', '.join(sorted(unknown))}")

        # Start from the full current config and overlay only the provided keys;
        # rebuilding through the constructor makes pydantic validate the new values
        updated_config = ModelSettings(**{**self.config.model_dump(), **kwargs})

        self.config = updated_config
        self.client = self.init_client()
        self.save_config()

        logging.info(f"Model settings updated: {', '.join(f'{k}={v}' for k, v in kwargs.items())}")
        return self.config

    def save_config(self) -> None:

        config_path = Path(self.config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to a temp file then swap, so a crash mid-write can't corrupt the config
        tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.config.model_dump(mode="json"), f, indent=4)
        tmp_path.replace(config_path)

        logging.info(f"Model config saved to {config_path}")

    
    def init_memory(self):
        pass
    
    def update_memory(self):
        pass
    
    def clear_excess_context_memory(self):
        pass
        
        
        
    
        
        
        
        