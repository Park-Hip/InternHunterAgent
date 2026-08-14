import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq

from src.core.config import settings

PROFILES = frozenset({"react", "sql_generation"})


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

    def provider_for(self, profile: str) -> str:
        """Resolve which provider serves one profile.

        A profile may override 'agent.provider' so a single profile can move providers
        while the other stays put - the shape T0015.6 settled on for its Gemini arm.
        """
        profile_cfg = self._profile_cfg(profile)
        provider = profile_cfg.get("provider", self.provider)
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError(
                f"Missing or empty 'agent.{profile}.provider' in config/settings.yaml"
            )
        return provider.lower().strip()

    def _profile_cfg(self, profile: str) -> dict[str, Any]:
        if profile not in PROFILES:
            raise ValueError(f"Unsupported agent model profile: {profile}")

        profile_cfg = self.agent_cfg.get(profile)
        if not isinstance(profile_cfg, dict):
            raise ValueError(f"Missing 'agent.{profile}' section in config/settings.yaml")

        return profile_cfg

    def build_model(self, profile: str = "react") -> BaseChatModel:
        profile_cfg = self._profile_cfg(profile)
        provider = self.provider_for(profile)

        model_name = profile_cfg.get("model")
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError(
                f"Missing or empty 'agent.{profile}.model' in config/settings.yaml"
            )

        common_kwargs: dict[str, Any] = {
            "temperature": profile_cfg.get("temperature", 0.2),
            "max_tokens": profile_cfg.get("max_tokens", 1024),
            "timeout": profile_cfg.get("timeout", 30),
            # The eval driver owns retry accounting while it runs; a branch that retries
            # underneath it corrupts the run's retry ledger.
            "max_retries": (
                0
                if os.getenv("EVAL_DRIVER_DISABLE_PROVIDER_RETRIES") == "1"
                else profile_cfg.get("max_retries", 2)
            ),
            "streaming": profile_cfg.get("streaming", False),
        }

        if provider == "groq":
            groq_kwargs: dict[str, Any] = {
                "model_name": model_name,
                **common_kwargs,
                "groq_api_key": settings.GROQ_API_KEY,
                "reasoning_format": profile_cfg.get("reasoning_format"),
            }
            reasoning_effort = profile_cfg.get("reasoning_effort")
            if isinstance(reasoning_effort, str) and reasoning_effort.strip():
                groq_kwargs["reasoning_effort"] = reasoning_effort
            return ChatGroq(**groq_kwargs)

        if provider == "deepseek":
            from langchain_deepseek import ChatDeepSeek

            if not settings.DEEPSEEK_API_KEY:
                raise ValueError(
                    f"agent.{profile}.provider is 'deepseek' but DEEPSEEK_API_KEY is unset"
                )

            deepseek_kwargs: dict[str, Any] = {
                "model": model_name,
                **common_kwargs,
                "api_key": settings.DEEPSEEK_API_KEY,
            }
            extra_body = deepseek_extra_body(thinking_mode(profile_cfg, profile))
            if extra_body:
                deepseek_kwargs["extra_body"] = extra_body
            return ChatDeepSeek(**deepseek_kwargs)

        raise ValueError(f"Unsupported provider: {provider}")


def thinking_mode(profile_cfg: dict[str, Any], profile: str) -> str:
    """Read the DeepSeek thinking switch, defaulting to the value T0027.1 measured.

    Thinking is the provider's default, and it ignores 'temperature' while it is on -
    which the sql_generation profile's determinism depends on.
    """
    thinking = profile_cfg.get("thinking", "disabled")
    if thinking not in {"disabled", "enabled"}:
        raise ValueError(
            f"agent.{profile}.thinking must be 'disabled' or 'enabled', got {thinking!r}"
        )
    return thinking


def deepseek_extra_body(thinking: str) -> dict[str, Any]:
    """'enabled' sends nothing, because thinking on is what the provider does by default."""
    return {"thinking": {"type": "disabled"}} if thinking == "disabled" else {}
