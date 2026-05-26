from langchain_groq import ChatGroq

from src.core.config import settings


class AgentProvider:
    def __init__(self) -> None:
        agent_cfg = settings.config_yaml.get("agent")
        if not isinstance(agent_cfg, dict):
            raise ValueError("Missing 'agent' section in config/settings.yaml")

        provider = agent_cfg.get("provider")
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("Missing or empty 'agent.provider' in config/settings.yaml")

        self.agent_cfg = agent_cfg
        self.provider = provider.lower().strip()

    def build_model(self) -> ChatGroq:
        if self.provider != "groq":
            raise ValueError(f"Unsupported provider: {self.provider}")

        groq_cfg = self.agent_cfg.get("groq")
        if not isinstance(groq_cfg, dict):
            raise ValueError("Missing 'agent.groq' section in config/settings.yaml")

        model_name = groq_cfg.get("model")
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("Missing or empty 'agent.groq.model' in config/settings.yaml")

        return ChatGroq(
            model_name=model_name,
            temperature=groq_cfg.get("temperature", 0.2),
            max_tokens=groq_cfg.get("max_tokens", 1024),
            timeout=groq_cfg.get("timeout", 30),
            max_retries=groq_cfg.get("max_retries", 2),
            streaming=groq_cfg.get("streaming", False),
            groq_api_key=settings.GROQ_API_KEY,
        )