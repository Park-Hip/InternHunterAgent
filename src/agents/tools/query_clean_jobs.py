import asyncio
from typing import Any

from langchain.messages import HumanMessage
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from src.agents.runtime.prompts import load_schema_context, load_sql_generation_prompt
from src.agents.runtime.provider import AgentProvider
from src.core.config import settings
from src.services.query.executor import ExecutorError, execute_validated_sql
from src.services.query.models import TableArtifact
from src.services.query.row_bound import resolve_bounds
from src.services.query.sql_validator import validate_sql
from src.services.query.table_formatter import format_rows


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


async def generate_sql(question: str, config: RunnableConfig | None = None) -> str:
    schema_context = load_schema_context()
    sql_generation_prompt = load_sql_generation_prompt()
    model = AgentProvider().build_model("sql_generation")

    response = await model.ainvoke(
        [HumanMessage(content=f"{sql_generation_prompt}\n\n{schema_context}\n\nQuestion: {question}")],
        config=config,
    )
    return _content_to_text(response.content).strip()


def _build_answer(table: TableArtifact) -> str:
    if table.row_count == 0:
        return "No matching internship job postings were found."

    if table.truncated:
        header = (
            f"Showing the first {table.row_count} results — there are more matches. "
            f"Narrow your search to see the rest. Columns: {', '.join(table.columns)}."
        )
    else:
        header = f"Found {table.row_count} result(s) with columns: {', '.join(table.columns)}."

    lines = [header]
    for row in table.rows:
        pairs = ", ".join(f"{column}={value}" for column, value in zip(table.columns, row))
        lines.append(f"- {pairs}")
    return "\n".join(lines)


@tool
async def query_clean_jobs(question: str, config: RunnableConfig) -> str:
    """Answer questions about internship job postings stored in the clean_jobs table."""
    sql = await generate_sql(question, config)
    validation = validate_sql(sql)

    if not validation.valid:
        return f"I can't run that query: {validation.reason}"

    max_rows = load_max_rows()
    bounds = resolve_bounds(validation.sql, max_rows)

    try:
        rows = await asyncio.to_thread(execute_validated_sql, bounds.sql)
    except ExecutorError:
        return "I couldn't retrieve the requested data due to a database error. Please try again later."

    table = format_rows(rows, bounds.display_cap)
    return _build_answer(table)
