"""Build the served agent models from the typed configuration resolved at load.

The deployment allowlist and the profiles live in ``config/settings.yaml`` and
are validated and resolved once by ``src/core/config.py``; this module reads
those typed objects and builds one ``ChatLiteLLM`` client per profile, at most
once per process.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_litellm import ChatLiteLLM

from src.core.config import ResolvedDeployment, get_configured_secret, settings

_built_models: dict[str, BaseChatModel] = {}


class ProviderCredentialError(ValueError):
    """A selected serving deployment has no usable API key. Refuses to serve."""


def _resolve_deployment_credential(deployment: ResolvedDeployment, profile: str) -> str:
    """Read one deployment's key for the boot guard and for model construction.

    The serving lifespan refuses to start when this raises, and ``build_model``
    raises the same way on every use, so the two cannot drift apart.
    """
    api_key = get_configured_secret(deployment.api_key_env)
    if api_key is None:
        raise ProviderCredentialError(
            f"agent.{profile}.deployment is '{deployment.name}' but "
            f"{deployment.api_key_env} is unset or empty. "
            "Set it in .env or the Render dashboard; see docs/how-to/operate.md."
        )
    return api_key


def assert_profile_credential(profile: str) -> None:
    """Refuse when the profile's selected deployment has no usable key.

    The serving lifespan calls this before the checkpointer pool opens, so a
    deploy that would fail every question refuses to start instead.
    """
    deployment = settings.agent.deployment_for(profile)
    _resolve_deployment_credential(deployment, profile)


def build_model(profile: str = "react") -> BaseChatModel:
    """Return the profile's model, built at most once per process.

    The credential is re-read on every call, so a key that disappears after
    boot refuses here exactly as the boot guard does; only the client
    construction is cached.
    """
    deployment = settings.agent.deployment_for(profile)
    api_key = _resolve_deployment_credential(deployment, profile)

    cached = _built_models.get(profile)
    if cached is not None:
        return cached

    profile_settings = deployment.profile
    model = ChatLiteLLM(
        model=deployment.model,
        api_key=api_key,
        temperature=profile_settings.temperature,
        max_tokens=profile_settings.max_tokens,
        request_timeout=profile_settings.timeout,
        # The configured value counts attempts, not retries: ChatLiteLLM feeds
        # it to tenacity's stop_after_attempt, so 2 is two requests and 1 is a
        # single attempt. That is why the YAML key is named max_attempts.
        max_retries=profile_settings.max_attempts,
        streaming=profile_settings.streaming,
        model_kwargs=deployment.options.to_model_kwargs(),
    )
    _built_models[profile] = model
    return model


def reset_built_models() -> None:
    """Drop the per-profile model cache.

    Production never calls this: one model per profile per process is the
    point. Tests call it between cases so a previously built client cannot
    leak through the cache into the next test.
    """
    _built_models.clear()
