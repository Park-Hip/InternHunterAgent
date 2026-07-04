from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq

from deepeval.models.base_model import DeepEvalBaseLLM
from src.core.config import settings


class DeepEvalJudge(DeepEvalBaseLLM):
    """DeepEvalBaseLLM wrapper around a LangChain chat model, used as the eval judge."""

    def __init__(self, chat_model: BaseChatModel, model_name: str) -> None:
        self._chat_model = chat_model
        self._model_name = model_name
        super().__init__(model=model_name)

    def load_model(self) -> BaseChatModel:
        return self._chat_model

    def generate(self, prompt: str) -> str:
        return str(self.load_model().invoke(prompt).content)

    async def a_generate(self, prompt: str) -> str:
        response = await self.load_model().ainvoke(prompt)
        return str(response.content)

    def get_model_name(self) -> str:
        return self._model_name


def _load_judge_cfg() -> dict:
    eval_cfg = settings.config_yaml.get("eval")
    if not isinstance(eval_cfg, dict):
        raise ValueError("Missing 'eval' section in config/settings.yaml")

    judge_cfg = eval_cfg.get("judge")
    if not isinstance(judge_cfg, dict):
        raise ValueError("Missing 'eval.judge' section in config/settings.yaml")

    return judge_cfg


def build_judge() -> DeepEvalJudge:
    judge_cfg = _load_judge_cfg()

    provider = judge_cfg.get("provider")
    if not isinstance(provider, str) or not provider.strip():
        raise ValueError("Missing or empty 'eval.judge.provider' in config/settings.yaml")
    provider = provider.lower().strip()

    model_name = judge_cfg.get("model")
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("Missing or empty 'eval.judge.model' in config/settings.yaml")

    temperature = judge_cfg.get("temperature", 0.0)

    if provider != "groq":
        raise ValueError(f"Unsupported 'eval.judge.provider': {provider}")

    chat_model: BaseChatModel = ChatGroq(
        model_name=model_name,
        temperature=temperature,
        max_tokens=1024,
        timeout=30,
        max_retries=2,
        streaming=False,
        groq_api_key=settings.GROQ_API_KEY,
    )
    return DeepEvalJudge(chat_model, model_name=f"groq/{model_name}")
