from pathlib import Path
import json
import logging

from app.core.config import ModelSettings
from app.llm.client import OllamaClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class ModelStateManager:
    
    def __init__(self, config_path: Path):
        
        self.config_path = config_path
        self.config = self.load_config
        # self.client = 
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
    
    def call_client(self) -> OllamaClient:
        
        ollama_client = OllamaClient(self.config.ollama_base_url)
    
    def update_client_params(self, **kwargs):
        pass
    
    def init_memory(self):
        pass
    
    def update_memory(self):
        pass
    
    def clear_excess_context_memory(self):
        pass
        
        
        
    
        
        
        
        