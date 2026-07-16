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

    def build_model(self, profile: str = "react"):
        if profile not in {"react", "sql_generation"}:
            raise ValueError(f"Unsupported agent model profile: {profile}")

        profile_cfg = self.agent_cfg.get(profile)
        if not isinstance(profile_cfg, dict):
            raise ValueError(f"Missing 'agent.{profile}' section in config/settings.yaml")

        model_name = profile_cfg.get("model")
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError(
                f"Missing or empty 'agent.{profile}.model' in config/settings.yaml"
            )

        provider = profile_cfg.get("provider", self.provider)
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError(
                f"Missing or empty 'agent.{profile}.provider' in config/settings.yaml"
            )
        provider = provider.lower().strip()

        common_kwargs = {
            "temperature": profile_cfg.get("temperature", 0.2),
            "max_tokens": profile_cfg.get("max_tokens", 1024),
            "timeout": profile_cfg.get("timeout", 30),
            "max_retries": profile_cfg.get("max_retries", 2),
            "streaming": profile_cfg.get("streaming", False),
        }

        if provider == "groq":
            model_kwargs = {
                "model_name": model_name,
                **common_kwargs,
                "groq_api_key": settings.GROQ_API_KEY,
                "reasoning_format": profile_cfg.get("reasoning_format"),
            }
            reasoning_effort = profile_cfg.get("reasoning_effort")
            if isinstance(reasoning_effort, str) and reasoning_effort.strip():
                model_kwargs["reasoning_effort"] = reasoning_effort
            return ChatGroq(**model_kwargs)

        if provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            if not settings.GOOGLE_API_KEY:
                raise ValueError(
                    f"agent.{profile}.provider is 'google' but GOOGLE_API_KEY is unset"
                )
            return ChatGoogleGenerativeAI(
                model=model_name,
                **common_kwargs,
                google_api_key=settings.GOOGLE_API_KEY,
                thinking_budget=profile_cfg.get("thinking_budget", 0),
            )

        raise ValueError(f"Unsupported provider: {provider}")
