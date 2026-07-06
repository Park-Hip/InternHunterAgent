import asyncio
import threading
import time

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq

from deepeval.models.base_model import DeepEvalBaseLLM
from src.core.config import settings

_RATE_WINDOW_SECONDS = 60.0


class _RpmThrottle:
    """Sliding-window limiter so the judge stays under its free-tier RPM
    instead of firing calls back-to-back and relying on 429 retries, which
    is what makes a ~120-call judge run (harness.py's score()) look stuck."""

    def __init__(self, rpm: int) -> None:
        self._rpm = rpm
        self._lock = threading.Lock()
        self._call_times: list[float] = []

    def _wait_seconds(self) -> float:
        if self._rpm <= 0:
            return 0.0
        with self._lock:
            now = time.monotonic()
            self._call_times = [t for t in self._call_times if now - t < _RATE_WINDOW_SECONDS]
            if len(self._call_times) < self._rpm:
                self._call_times.append(now)
                return 0.0
            wait = _RATE_WINDOW_SECONDS - (now - self._call_times[0])
            self._call_times.append(now + wait)
            return max(wait, 0.0)

    def wait(self) -> None:
        time.sleep(self._wait_seconds())

    async def a_wait(self) -> None:
        await asyncio.sleep(self._wait_seconds())


class DeepEvalJudge(DeepEvalBaseLLM):
    """DeepEvalBaseLLM wrapper around a LangChain chat model, used as the eval judge."""

    def __init__(self, chat_model: BaseChatModel, model_name: str, rpm: int = 0) -> None:
        self._chat_model = chat_model
        self._model_name = model_name
        self._throttle = _RpmThrottle(rpm)
        super().__init__(model=model_name)

    def load_model(self) -> BaseChatModel:
        return self._chat_model

    def generate(self, prompt: str) -> str:
        self._throttle.wait()
        return str(self.load_model().invoke(prompt).content)

    async def a_generate(self, prompt: str) -> str:
        await self._throttle.a_wait()
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
    rpm = judge_cfg.get("rpm", 0)

    if provider == "groq":
        chat_model: BaseChatModel = ChatGroq(
            model_name=model_name,
            temperature=temperature,
            max_tokens=1024,
            timeout=30,
            max_retries=2,
            streaming=False,
            groq_api_key=settings.GROQ_API_KEY,
        )
        return DeepEvalJudge(chat_model, model_name=f"groq/{model_name}", rpm=rpm)
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.GOOGLE_API_KEY:
            raise ValueError("eval.judge.provider is 'google' but GOOGLE_API_KEY is unset")

        chat_model = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            max_tokens=4096,
            timeout=30,
            max_retries=2,
            google_api_key=settings.GOOGLE_API_KEY,
        )
        return DeepEvalJudge(chat_model, model_name=f"google/{model_name}", rpm=rpm)
    else:
        raise ValueError(f"Unsupported 'eval.judge.provider': {provider}")
