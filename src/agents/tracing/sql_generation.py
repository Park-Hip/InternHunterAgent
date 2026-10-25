"""The traced model client the query service calls to write one SQL statement.

The query service owns prompt assembly, so this adapter owns only the model call
and its observability. Keeping both branches here means ``src/services/query/``
imports no Langfuse code, and the tool imports no Langfuse symbol directly.

Inside a LangChain agent, MCP does not transport ``RunnableConfig`` into the
tool, so reading the ambient config preserves the nested SQL generation for
Langfuse and DeepEval callbacks. A plain MCP client has no ambient config, so it
gets one explicit generation instead; with tracing disabled the call is plain.
"""

from __future__ import annotations

from typing import Any

from langchain.messages import HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import var_child_runnable_config

from src.agents.tracing.langfuse import (
    get_langfuse_client,
    langfuse_prompt_attributes,
)
from src.agents.tracing.prompt_registry import ResolvedPrompt
from src.core.config import settings
from src.services.query.generator import SqlGenerationModel

SQL_GENERATION_OBSERVATION_NAME = "sql_generation"


class TracedSqlGenerationModel(SqlGenerationModel):
    """One ``sql_generation`` model call with its prompt lineage attached."""

    def __init__(
        self,
        *,
        model: BaseChatModel,
        request: str,
        sql_generation_prompt: ResolvedPrompt,
    ) -> None:
        self._model = model
        self._request = request
        self._prompt = sql_generation_prompt

    async def complete(self, prompt: str) -> str:
        """Run the model and return its reply text, stripped for validation."""
        messages = [HumanMessage(content=prompt)]

        ambient_config = _ambient_langchain_config()
        if ambient_config is not None:
            with langfuse_prompt_attributes(self._prompt):
                response = await self._model.ainvoke(messages, config=ambient_config)
            return _content_to_text(response.content)

        client = get_langfuse_client()
        if client is None:
            response = await self._model.ainvoke(messages)
            return _content_to_text(response.content)

        with client.start_as_current_observation(
            as_type="generation",
            name=SQL_GENERATION_OBSERVATION_NAME,
            model=settings.agent.deployment_for("sql_generation").model,
            input={"question": self._request},
            prompt=self._prompt.prompt_client,
        ) as generation:
            response = await self._model.ainvoke(messages)
            generation.update(output=_content_to_text(response.content))

        return _content_to_text(response.content)


def _content_to_text(content: str | list[Any]) -> str:
    """Flatten a text or block-list reply to its stripped text."""
    if isinstance(content, str):
        return content.strip()

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text", "")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts).strip()


def _ambient_langchain_config() -> RunnableConfig | None:
    # A tool running inside a LangChain agent exposes the ambient config here
    # even though MCP does not transport RunnableConfig into the tool.
    config = var_child_runnable_config.get()
    if config is None:
        return None
    callbacks = config.get("callbacks")
    if not callbacks:
        return None
    return {"callbacks": callbacks}
