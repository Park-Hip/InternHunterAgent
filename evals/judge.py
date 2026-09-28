"""Shared LLM judge for the evaluation harness.

One provider, ``max_retries=2``, no RPM throttle. The throttle is deleted
because a paid model does not need a sliding-window limiter; the SDK's
built-in retry is sufficient.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq

from deepeval.models.base_model import DeepEvalBaseLLM
from src.core.config import settings

_judge_cache: dict[str, DeepEvalBaseLLM] = {}


class DeepEvalJudge(DeepEvalBaseLLM):
    """Minimal DeepEvalBaseLLM wrapper around one LangChain chat model."""

    def __init__(self, chat_model: BaseChatModel, model_name: str) -> None:
        self._chat_model = chat_model
        self._model_name = model_name
        super().__init__(model=model_name)

    @staticmethod
    def _content_to_text(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                elif getattr(block, "type", None) == "text":
                    parts.append(str(getattr(block, "text", "")))
            return "\n".join(p for p in parts if p)
        return str(content)

    def load_model(self) -> BaseChatModel:
        return self._chat_model

    def generate(self, prompt: str) -> str:
        return self._content_to_text(self.load_model().invoke(prompt).content)

    async def a_generate(self, prompt: str) -> str:
        response = await self.load_model().ainvoke(prompt)
        return self._content_to_text(response.content)

    def get_model_name(self) -> str:
        return self._model_name


def build_judge() -> DeepEvalBaseLLM:
    """Build the shared judge from ``config/settings.yaml``::eval::judge."""
    eval_cfg = settings.config_yaml.get("eval")
    if not isinstance(eval_cfg, dict):
        raise ValueError("Missing 'eval' section in config/settings.yaml")
    judge_cfg = eval_cfg.get("judge")
    if not isinstance(judge_cfg, dict):
        raise ValueError("Missing 'eval.judge' section in config/settings.yaml")

    provider = (judge_cfg.get("provider") or "").strip().lower()
    model_name = str(judge_cfg.get("model") or "").strip()
    if not provider:
        raise ValueError("Missing or empty 'eval.judge.provider' in config/settings.yaml")
    if not model_name:
        raise ValueError("Missing or empty 'eval.judge.model' in config/settings.yaml")

    temperature = judge_cfg.get("temperature", 0.0)
    timeout = judge_cfg.get("timeout_seconds", 30)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("eval.judge.timeout_seconds must be a positive number")

    max_tokens_map: dict[str, int] = {
        k: int(v)
        for k, v in (judge_cfg.get("providers") or {}).items()
        if isinstance(v, (int, float))
    }

    if provider == "groq":
        if not settings.GROQ_API_KEY:
            raise ValueError("eval.judge.provider is 'groq' but GROQ_API_KEY is unset")
        chat_model: BaseChatModel = ChatGroq(
            model_name=model_name,
            temperature=float(temperature),
            max_tokens=int(max_tokens_map.get("groq", 1024)),
            timeout=float(timeout),
            max_retries=2,
            streaming=False,
            groq_api_key=settings.GROQ_API_KEY,
        )
        return DeepEvalJudge(chat_model, model_name=f"groq/{model_name}")
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.GOOGLE_API_KEY:
            raise ValueError(
                "eval.judge.provider is 'google' but GOOGLE_API_KEY is unset"
            )
        chat_model = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=float(temperature),
            max_tokens=int(max_tokens_map.get("google", 4096)),
            timeout=float(timeout),
            max_retries=2,
            google_api_key=settings.GOOGLE_API_KEY,
        )
        return DeepEvalJudge(chat_model, model_name=f"google/{model_name}")
    elif provider == "openrouter":
        from langchain_openai import ChatOpenAI

        if not settings.OPENROUTER_API_KEY:
            raise ValueError(
                "eval.judge.provider is 'openrouter' but OPENROUTER_API_KEY is unset"
            )
        chat_model = ChatOpenAI(
            model=model_name,
            base_url="https://openrouter.ai/api/v1",
            temperature=float(temperature),
            max_tokens=int(max_tokens_map.get("openrouter", 4096)),
            timeout=float(timeout),
            max_retries=2,
            openai_api_key=settings.OPENROUTER_API_KEY,
        )
        return DeepEvalJudge(chat_model, model_name=f"openrouter/{model_name}")
    else:
        raise ValueError(
            f"Unknown eval.judge.provider {provider!r}; expected groq/google/openrouter"
        )


def get_judge() -> DeepEvalBaseLLM:
    """Return the cached shared judge instance."""
    cfg = settings.config_yaml.get("eval", {}).get("judge", {})
    key = f"{cfg.get('provider')}:{cfg.get('model')}"
    if key not in _judge_cache:
        _judge_cache[key] = build_judge()
    return _judge_cache[key]
