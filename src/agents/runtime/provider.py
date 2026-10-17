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


class ProviderCredentialError(ValueError):
    """A selected serving deployment has no usable API key. Refuses to serve."""


def _resolve_deployment_credential(deployment: AgentDeployment, profile: str) -> str:
    """Read one deployment's key for the boot guard and for model construction.

    The serving lifespan refuses to start when this raises, and ``build_model``
    raises the same way on first use, so the two cannot drift apart.
    """
    api_key = get_configured_secret(deployment.api_key_env)
    if api_key is None:
        raise ProviderCredentialError(
            f"agent.{profile}.deployment is '{deployment.name}' but "
            f"{deployment.api_key_env} is unset or empty. "
            "Set it in .env or the Render dashboard; see docs/how-to/operate.md."
        )
    return api_key


def provider_options_to_model_kwargs(deployment: AgentDeployment) -> dict[str, Any]:
    """Translate validated, provider-specific options for LiteLLM's request shape."""

    options = deployment.provider_options
    if deployment.provider == "deepseek":
        thinking = options.get("thinking", "disabled")
        if thinking == "disabled":
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        return {}
    return dict(options)


class AgentProvider:
    """Build trusted profile deployments through the provider-neutral LiteLLM adapter."""

    def deployment_for(self, profile: str) -> AgentDeployment:
        return resolve_agent_deployment(settings.config_yaml, profile)

    def provider_for(self, profile: str) -> str:
        """Return the LiteLLM provider selected for one runtime profile."""

        return self.deployment_for(profile).provider

    def assert_profile_credential(self, profile: str) -> None:
        """Refuse when the profile's selected deployment has no usable key.

        The serving lifespan calls this before the checkpointer pool opens, so a
        deploy that would fail every question refuses to start instead.
        """
        _resolve_deployment_credential(self.deployment_for(profile), profile)

    def build_model(self, profile: str = "react") -> BaseChatModel:
        deployment = self.deployment_for(profile)
        api_key = _resolve_deployment_credential(deployment, profile)

        profile_config = deployment.profile
        # The configured value counts attempts, not retries: ChatLiteLLM feeds
        # it to tenacity's stop_after_attempt, so 2 is two requests and 1 is a
        # single attempt. That is why the YAML key is named max_attempts.
        max_attempts = (
            1
            if os.getenv("EVAL_DRIVER_DISABLE_PROVIDER_RETRIES") == "1"
            else profile_config["max_attempts"]
        )
        return ChatLiteLLM(
            model=deployment.model,
            api_key=api_key,
            temperature=profile_config["temperature"],
            max_tokens=profile_config["max_tokens"],
            request_timeout=profile_config["timeout"],
            max_retries=max_attempts,
            streaming=profile_config["streaming"],
            model_kwargs=provider_options_to_model_kwargs(deployment),
        )
