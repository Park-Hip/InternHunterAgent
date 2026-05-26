from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Any
from pathlib import Path
from pydantic import Field
import yaml

class Settings(BaseSettings):
    GROQ_API_KEY: str = Field(..., min_length=1)

    LANGFUSE_SECRET_KEY: str
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_BASE_URL: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",extra="ignore")

    config_yaml: Dict[str, Any] = {}
    prompts_yaml: Dict[str, Any] = {}

def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"Missing config file: {path}")
    
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {path}: expected a mapping/object")

    return data

def load_settings() -> Settings:
    settings = Settings()
    
    settings.config_yaml = _load_yaml_file(Path("config/settings.yaml"))
    settings.prompts_yaml = _load_yaml_file(Path("config/prompts.yaml"))
            
    return settings

settings = load_settings()