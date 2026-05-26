from langchain_groq import ChatGroq
from src.core.config import settings

class AgentProvider():
    def __init__(self):
        self.provider = settings.config_yaml["agent"]["provider"].lower()

    def build_model(self):
        if self.provider != "groq":
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        groq_cfg = settings.config_yaml["agent"]["groq"]
        
        if self.provider == 'groq':
            return ChatGroq(
            model_name=groq_cfg["model"],
            temperature=groq_cfg.get("temperature", 0.2),
            max_tokens=groq_cfg.get("max_tokens", 1024),
            timeout=groq_cfg.get("timeout", 30),
            max_retries=groq_cfg.get("max_retries", 2),
            streaming=groq_cfg.get("streaming", False),
            groq_api_key=settings.GROQ_API_KEY,
        )