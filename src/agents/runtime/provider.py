import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_litellm import ChatLiteLLM

from src.core.config import (
    AgentDeployment,
    get_configured_secret,
    resolve_agent_deployment,
    settings,
)


def provider_options_to_model_kwargs(deployment: AgentDeployment) -> dict[str, Any]:
    """Translate validated, provider-specific options for LiteLLM's request shape."""

    options = deployment.provider_options
    if deployment.provider == "deepseek":
        thinking = options.get("thinking", "disabled")
        if thinking == "disabled":
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        return {}
    if deployment.provider == "groq":
        model_kwargs: dict[str, Any] = {}
        if "reasoning_effort" in options:
            model_kwargs["reasoning_effort"] = options["reasoning_effort"]
            model_kwargs["allowed_openai_params"] = ["reasoning_effort"]
        if "reasoning_format" in options:
            model_kwargs["extra_body"] = {
                "reasoning_format": options["reasoning_format"]
            }
        return model_kwargs
    return dict(options)


class AgentProvider:
    """Build trusted profile deployments through the provider-neutral LiteLLM adapter."""

    def deployment_for(self, profile: str) -> AgentDeployment:
        return resolve_agent_deployment(settings.config_yaml, profile)

    def provider_for(self, profile: str) -> str:
        """Return the LiteLLM provider selected for one runtime profile."""

        return self.deployment_for(profile).provider

    def build_model(self, profile: str = "react") -> BaseChatModel:
        deployment = self.deployment_for(profile)
        api_key = get_configured_secret(deployment.api_key_env)
        if api_key is None:
            raise ValueError(
                f"agent.{profile}.deployment is '{deployment.name}' but "
                f"{deployment.api_key_env} is unset"
            )

        profile_config = deployment.profile
        max_retries = (
            0
            if os.getenv("EVAL_DRIVER_DISABLE_PROVIDER_RETRIES") == "1"
            else profile_config["max_retries"]
        )
        return ChatLiteLLM(
            model=deployment.model,
            api_key=api_key,
            temperature=profile_config["temperature"],
            max_tokens=profile_config["max_tokens"],
            request_timeout=profile_config["timeout"],
            max_retries=max_retries,
            streaming=profile_config["streaming"],
            model_kwargs=provider_options_to_model_kwargs(deployment),
        )
