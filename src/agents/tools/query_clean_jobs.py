"""Framework-neutral implementation of the read-only clean-jobs search ability.

This module owns the single source of truth for natural-language-to-SQL
generation, validation, execution, formatting, and the safe Vietnamese error
policy. The MCP tool wrapper (see src/agents/mcp/job_server.py) calls
``run_query_clean_jobs`` directly; the LangChain agent reaches the same
implementation through the in-process MCP adapter.

Nothing here depends on LangChain tool decoration or a transportable
``RunnableConfig``. The SQL generation reads LangChain's ambient config when
one is present (so nested callbacks keep observing it within an agent), and
falls back to an explicit Langfuse generation otherwise, so the function works
identically for a plain MCP client with no LangChain context.
"""

import asyncio
from typing import Any

from langchain.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import var_child_runnable_config

from src.agents.runtime.prompts import (
    load_behavior_glossary,
    load_schema_context_resolution_async,
    load_sql_generation_prompt_resolution_async,
)
from src.agents.runtime.provider import AgentProvider
from src.agents.runtime.tool_events import publish_tool_result
from src.agents.tracing.langfuse import get_langfuse_client, langfuse_prompt_attributes
from src.core.config import settings
from src.core.logger import logger
from src.services.query.executor import (
    ExecutorError,
    UndefinedColumnError,
    execute_validated_sql,
)
from src.services.query.models import QueryRefusal, QueryToolResult
from src.services.query.obligations import (
    detect_obligations,
    filter_enabled_obligations,
)
from src.services.query.row_bound import resolve_bounds
from src.services.query.sql_validator import validate_sql
from src.services.query.table_formatter import format_rows, render_tool_result

SQL_GENERATION_OBSERVATION_NAME = "sql_generation"


def load_max_rows() -> int:
    agent_cfg = settings.config_yaml.get("agent")
    if not isinstance(agent_cfg, dict):
        raise ValueError("Missing 'agent' section in config/settings.yaml")

    query_cfg = agent_cfg.get("query")
    if not isinstance(query_cfg, dict):
        raise ValueError("Missing 'agent.query' section in config/settings.yaml")

    max_rows = query_cfg.get("max_rows")
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows <= 0:
        raise ValueError(
            "agent.query.max_rows must be a positive integer in config/settings.yaml"
        )

    return max_rows


def _content_to_text(content: str | list[Any]) -> str:
    if isinstance(content, str):
        return content

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text", "")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


async def generate_sql(question: str) -> str:
    """Generate SQL for one question with an explicit traceable generation."""
    provider = AgentProvider()
    schema_context = await load_schema_context_resolution_async()
    sql_generation_prompt = await load_sql_generation_prompt_resolution_async()
    model = provider.build_model("sql_generation")
    messages = [
        HumanMessage(
            content=(
                f"{sql_generation_prompt.content}\n\n{schema_context.content}"
                f"\n\nQuestion: {question}"
            )
        )
    ]

    # Inside a LangChain agent, MCP does not transport RunnableConfig into the
    # tool, so reading the ambient config here preserves the nested SQL
    # generation for Langfuse and DeepEval callbacks exactly as the previous
    # decorated tool did by forwarding its injected config.
    ambient_config = _ambient_langchain_config()
    if ambient_config is not None:
        with langfuse_prompt_attributes(sql_generation_prompt):
            response = await model.ainvoke(messages, config=ambient_config)
        return _content_to_text(response.content).strip()

    # No ambient LangChain config (a plain MCP client over Streamable HTTP).
    # Emit an explicit Langfuse generation so the SQL call stays observable.
    client = get_langfuse_client()
    if client is None:
        response = await model.ainvoke(messages)
        return _content_to_text(response.content).strip()

    with client.start_as_current_observation(
        as_type="generation",
        name=SQL_GENERATION_OBSERVATION_NAME,
        model=provider.deployment_for("sql_generation").model,
        input={"question": question},
        prompt=sql_generation_prompt.prompt_client,
    ) as generation:
        response = await model.ainvoke(messages)
        generation.update(output=_content_to_text(response.content).strip())

    return _content_to_text(response.content).strip()


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


async def run_query_clean_jobs(question: str) -> str:
    """Return safe Vietnamese clean_jobs search results for one question."""
    sql = await generate_sql(question)
    validation = validate_sql(sql)

    if not validation.valid:
        logger.warning("query_clean_jobs.sql_rejected", reason=validation.reason)
        # A rejected query is not a search that matched nothing. Publishing zero
        # here would show the reader "no results" for a question never asked of
        # the database.
        publish_tool_result(row_count=None)
        return f"Tôi không thể chạy truy vấn đó: {validation.reason}"

    max_rows = load_max_rows()
    bounds = resolve_bounds(validation.sql, max_rows)

    try:
        rows = await asyncio.to_thread(execute_validated_sql, bounds.sql)
    except UndefinedColumnError as exc:
        logger.warning("query_clean_jobs.unknown_column", error=str(exc))
        # A refused query matched nothing, but it is a refusal rather than an
        # empty result, so publish no count rather than a misleading zero.
        publish_tool_result(row_count=None)
        return render_tool_result(
            QueryToolResult(
                refusal=QueryRefusal(reason="", glossary_token="ABSENT_FIELD")
            ),
            load_behavior_glossary(),
        )
    except ExecutorError as exc:
        logger.error("query_clean_jobs.db_error", error=str(exc))
        publish_tool_result(row_count=None)
        return "Tôi không thể truy xuất dữ liệu do lỗi cơ sở dữ liệu. Vui lòng thử lại sau."

    table = format_rows(rows, bounds.display_cap)
    # The row count survives only inside a sentence once the table is rendered for
    # the model. Publish it as a fact too, so the interface can show the real number
    # instead of leaving the reader to infer it from prose.
    publish_tool_result(row_count=table.row_count, truncated=table.truncated)
    obligations = filter_enabled_obligations(detect_obligations(validation.sql, table))
    return render_tool_result(
        QueryToolResult(table=table, obligations=obligations),
        load_behavior_glossary(),
    )