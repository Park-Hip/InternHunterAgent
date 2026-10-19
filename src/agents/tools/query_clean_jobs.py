"""Framework-neutral implementation of the read-only clean-jobs search ability.

This module owns the single source of truth for natural-language-to-SQL
generation, validation, execution, and the typed result. The MCP tool wrapper
(see src/agents/mcp/job_server.py) calls ``run_query_clean_jobs`` directly; the
LangChain agent reaches the same implementation through the in-process MCP
adapter.

The tool returns facts, never sentences (#702): the SQL that ran, the columns,
the rows, and the real match total. The system prompt owns every user-facing
word. Failures are raised as :class:`ToolFailure` and reach the model as
error-status tool messages.

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
    load_schema_context_resolution_async,
    load_sql_generation_prompt_resolution_async,
)
from src.agents.runtime.provider import build_model
from src.agents.runtime.tool_events import publish_tool_result
from src.agents.tools.failures import ToolFailure
from src.agents.tracing.langfuse import get_langfuse_client, langfuse_prompt_attributes
from src.core.config import settings
from src.core.logger import logger
from src.services.query.executor import (
    ExecutorError,
    PermissionDeniedError,
    QueryTimeoutError,
    ResultTooLargeError,
    UndefinedColumnError,
    execute_bounded_select,
)
from src.services.query.models import QueryResult
from src.services.query.result_shape import classify_result_shape, counted_total
from src.services.query.row_bound import resolve_bounds
from src.services.query.sql_validator import validate_sql
from src.services.query.table_formatter import shape_rows

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
    schema_context = await load_schema_context_resolution_async()
    sql_generation_prompt = await load_sql_generation_prompt_resolution_async()
    model = build_model("sql_generation")
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
        model=settings.agent.deployment_for("sql_generation").model,
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


def _publish_result_facts(sql: str, result: QueryResult) -> None:
    # Publish what this tool knows about its result, and nothing it does not.
    # A listing's count is the real match total, so the interface shows "20 of
    # 161" rather than the shown rows only. A count query's single row holds
    # the total, so publish that total; any other summary publishes no count,
    # so the interface cannot state a figure the answer does not (#677).
    shape = classify_result_shape(sql)
    if shape == "match_count":
        publish_tool_result(
            row_count=counted_total(result.columns, result.rows), truncated=False
        )
    elif shape == "rows":
        publish_tool_result(
            row_count=result.total_rows,
            truncated=result.row_count < result.total_rows,
        )
    else:
        # Absent, not zero: the query ran, but it has no match count to state.
        publish_tool_result(row_count=None)


async def run_query_clean_jobs(request: str) -> QueryResult:
    """Return typed clean_jobs facts for one standalone request.

    The request is generated by the agent: one standalone statement that
    restates every filter from earlier turns that still applies.
    """
    sql = await generate_sql(request)
    validation = validate_sql(sql)

    if not validation.valid:
        logger.warning("query_clean_jobs.sql_rejected", reason=validation.reason)
        # A rejection is not a search that matched nothing, so no count is
        # published: the tool raises and the card reports the error instead.
        raise ToolFailure("rejected", validation.reason)

    max_rows = load_max_rows()
    bounds = resolve_bounds(validation.sql, max_rows)
    bounded_sql = f"{bounds.base_sql} LIMIT {bounds.limit}"
    if bounds.offset:
        bounded_sql += f" OFFSET {bounds.offset}"

    try:
        bounded = await asyncio.to_thread(
            execute_bounded_select,
            bounds.base_sql,
            bounds.limit,
            bounds.offset,
        )
    except UndefinedColumnError as exc:
        logger.warning("query_clean_jobs.unknown_column", error=str(exc))
        raise ToolFailure("unknown_column", exc.message_primary) from exc
    except QueryTimeoutError as exc:
        logger.warning("query_clean_jobs.timeout", error=str(exc))
        raise ToolFailure("timeout", str(exc)) from exc
    except ResultTooLargeError as exc:
        logger.warning("query_clean_jobs.too_large", error=str(exc))
        raise ToolFailure(
            "too_large", "result exceeds the byte budget; select fewer columns"
        ) from exc
    except PermissionDeniedError as exc:
        # The database refused a star, whole-row, or off-contract read (#722).
        # `rejected` is the honest kind: the refusal is deterministic and the
        # detail names the action, unlike `unavailable` (transient) or
        # `unknown_column` (a name the schema does not have).
        logger.warning("query_clean_jobs.column_denied", error=str(exc))
        raise ToolFailure(
            "rejected",
            "the query reads beyond the 16 declared columns; select those "
            "columns explicitly instead of using * or a whole-row expression",
        ) from exc
    except ExecutorError as exc:
        logger.error("query_clean_jobs.db_error", error=str(exc))
        raise ToolFailure(
            "unavailable", "the database could not run the query"
        ) from exc

    columns, rows = shape_rows(bounded.columns, bounded.rows)
    result = QueryResult(
        sql=bounded_sql,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        total_rows=bounded.total_rows,
    )
    _publish_result_facts(bounded_sql, result)
    return result
