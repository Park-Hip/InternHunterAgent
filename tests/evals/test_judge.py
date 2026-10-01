"""No-network unit tests for `evals/judge.py`'s config-to-model wiring.

Constructing a chat model with a dummy key does not reach the network — the
key is only validated on invoke — so these run in the plain suite rather than
behind the `eval` marker.

The point of these tests is the failure direction. A judge that silently
falls back to a default, or that builds a model without a credential, turns
a live eval run into a confident wrong answer instead of a stopped run.
"""

from __future__ import annotations

import pytest

from evals.judge import build_judge
from src.core.config import settings


def judge_config(**overrides: object) -> dict[str, object]:
    cfg: dict[str, object] = {"provider": "openrouter", "model": "ox-alpha", "temperature": 0.0}
    cfg.update(overrides)
    return {"eval": {"judge": cfg}}


def test_build_judge_targets_openrouter_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "dummy-key")
    monkeypatch.setattr(settings, "config_yaml", judge_config())
    judge = build_judge()
    assert judge.get_model_name() == "openrouter/ox-alpha"
    assert str(judge._chat_model.openai_api_base).rstrip("/") == "https://openrouter.ai/api/v1"


def test_missing_eval_section_is_reported_not_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "config_yaml", {})
    with pytest.raises(ValueError, match="Missing 'eval' section"):
        build_judge()


def test_missing_judge_section_is_reported_not_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "config_yaml", {"eval": {}})
    with pytest.raises(ValueError, match="Missing 'eval.judge' section"):
        build_judge()


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_missing_provider_is_rejected(monkeypatch: pytest.MonkeyPatch, blank: object) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "dummy-key")
    monkeypatch.setattr(settings, "config_yaml", judge_config(provider=blank))
    with pytest.raises(ValueError, match="'eval.judge.provider'"):
        build_judge()


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_missing_model_is_rejected(monkeypatch: pytest.MonkeyPatch, blank: object) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "dummy-key")
    monkeypatch.setattr(settings, "config_yaml", judge_config(model=blank))
    with pytest.raises(ValueError, match="'eval.judge.model'"):
        build_judge()


@pytest.mark.parametrize("timeout", [0, -1, -0.5, "thirty", None])
def test_non_positive_or_non_numeric_timeout_is_rejected(monkeypatch: pytest.MonkeyPatch, timeout: object) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "dummy-key")
    monkeypatch.setattr(settings, "config_yaml", judge_config(timeout_seconds=timeout))
    with pytest.raises(ValueError, match="timeout_seconds must be a positive number"):
        build_judge()


def test_unset_groq_key_stops_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GROQ_API_KEY", None)
    monkeypatch.setattr(settings, "config_yaml", judge_config(provider="groq"))
    with pytest.raises(ValueError, match="GROQ_API_KEY is unset"):
        build_judge()


def test_unset_google_key_stops_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """The configured provider is google on AI Studio; this is the live path."""
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", None)
    monkeypatch.setattr(settings, "config_yaml", judge_config(provider="google", model="gemma-4-31b-it"))
    with pytest.raises(ValueError, match="GOOGLE_API_KEY is unset"):
        build_judge()


def test_unset_openrouter_key_stops_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(settings, "config_yaml", judge_config())
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY is unset"):
        build_judge()


def test_unknown_provider_names_the_supported_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "config_yaml", judge_config(provider="anthropic"))
    with pytest.raises(ValueError, match="expected groq/google/openrouter"):
        build_judge()


def test_provider_name_is_normalized_before_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Config casing must not turn a valid provider into an unknown one."""
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "dummy-key")
    monkeypatch.setattr(settings, "config_yaml", judge_config(provider="  OpenRouter  "))
    assert build_judge().get_model_name() == "openrouter/ox-alpha"
