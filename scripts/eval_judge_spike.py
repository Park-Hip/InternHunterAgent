"""Throwaway spike (T0011.1): pick a DeepEval judge that reliably returns schema-valid JSON.

Groq retired llama-3.3-70b-versatile (shutdown 2026-08-16). Its named replacements
(openai/gpt-oss-120b, qwen/qwen3.6-27b) have reported structured-output regressions on
Groq. DeepEval's LLM-judged metrics hard-fail without valid JSON, so before building any
golden/metric work we run a live probe: wrap each candidate as a DeepEval custom LLM, run
one real GEval metric, and see whether it can parse a score out.

Not imported by anything else; not part of the harness. Discard once config/settings.yaml
eval.judge.* is set to the winner.
"""

from __future__ import annotations

import os
import sys
import traceback

from deepeval.metrics import GEval
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, SingleTurnParams
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq


class SpikeJudge(DeepEvalBaseLLM):
    """Minimal DeepEvalBaseLLM wrapper around a LangChain chat model, for spike use only."""

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


def run_probe(judge: DeepEvalBaseLLM) -> tuple[bool, str]:
    """Run a trivial GEval metric against the judge; return (passed, detail)."""
    test_case = LLMTestCase(
        input="Say hello to a new user.",
        actual_output="Hi there! It's great to have you here.",
    )
    metric = GEval(
        name="PoliteGreeting",
        criteria="Is the output a polite greeting? Score 0-1.",
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=judge,
    )
    try:
        metric.measure(test_case)
        return True, f"score={metric.score} reason={metric.reason!r}"
    except Exception as exc:  # noqa: BLE001 - spike wants any structured-output failure
        return False, f"{type(exc).__name__}: {exc}"


def probe_groq(model_name: str) -> tuple[bool, str]:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return False, "GROQ_API_KEY not set in environment"
    chat_model = ChatGroq(
        model_name=model_name,
        temperature=0.0,
        max_tokens=1024,
        timeout=30,
        max_retries=2,
        streaming=False,
        groq_api_key=api_key,
    )
    judge = SpikeJudge(chat_model, model_name=f"groq/{model_name}")
    return run_probe(judge)


def probe_gemini(model_name: str) -> tuple[bool, str]:
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return False, "GOOGLE_API_KEY not set in environment"
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        return False, f"langchain-google-genai not installed: {exc}"
    chat_model = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0.0,
        google_api_key=api_key,
    )
    judge = SpikeJudge(chat_model, model_name=f"google/{model_name}")
    return run_probe(judge)


def main() -> None:
    candidates = [
        ("groq", "openai/gpt-oss-120b", lambda: probe_groq("openai/gpt-oss-120b")),
        ("groq", "qwen/qwen3.6-27b", lambda: probe_groq("qwen/qwen3.6-27b")),
    ]

    winner: tuple[str, str] | None = None
    for provider, model_name, probe in candidates:
        try:
            passed, detail = probe()
        except Exception as exc:  # noqa: BLE001 - surface any unexpected failure as FAIL
            passed, detail = False, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        verdict = "PASS" if passed else "FAIL"
        print(f"{provider} {model_name} -> {verdict} ({detail})")
        if passed and winner is None:
            winner = (provider, model_name)

    if winner is None:
        print("Both Groq candidates FAILED. Falling back to Gemini free tier.")
        gemini_model = "gemini-2.0-flash"
        try:
            passed, detail = probe_gemini(gemini_model)
        except Exception as exc:  # noqa: BLE001
            passed, detail = False, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        verdict = "PASS" if passed else "FAIL"
        print(f"google {gemini_model} -> {verdict} ({detail})")
        if passed:
            winner = ("google", gemini_model)

    if winner is None:
        print("RECOMMENDATION: none of the candidates produced valid JSON. See failures above.")
        sys.exit(1)

    provider, model_name = winner
    print(f"RECOMMENDATION: provider={provider} model={model_name}")


if __name__ == "__main__":
    main()
