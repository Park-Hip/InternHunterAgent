import asyncio
from typing import Any

from langchain.messages import HumanMessage
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from src.agents.runtime.prompts import (
    load_behavior_glossary,
    load_schema_context,
    load_sql_generation_prompt,
)
from src.agents.runtime.provider import AgentProvider
from src.core.config import settings
from src.core.logger import logger
from src.services.query.executor import ExecutorError, UndefinedColumnError, execute_validated_sql
from src.services.query.models import QueryRefusal, QueryToolResult, TableArtifact
from src.services.query.obligations import detect_obligations, filter_enabled_obligations
from src.services.query.row_bound import resolve_bounds
from src.services.query.sql_validator import validate_sql
from src.services.query.table_formatter import format_rows, render_tool_result


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
        return load_behavior_glossary()["ZERO_RESULTS"]

    if table.truncated:
        header = (
            f"Đang hiển thị {table.row_count} kết quả đầu tiên - vẫn còn kết quả phù hợp. "
            f"Thu hẹp phạm vi tìm kiếm để xem phần còn lại. Các cột: {', '.join(table.columns)}."
        )
    else:
        header = f"Tìm thấy {table.row_count} kết quả với các cột: {', '.join(table.columns)}."

    lines = [header]
    for row in table.rows:
        pairs = ", ".join(f"{column}={value}" for column, value in zip(table.columns, row))
        lines.append(f"- {pairs}")
    return "\n".join(lines)


@tool
async def query_clean_jobs(question: str, config: RunnableConfig) -> str:
    """Search AI and data job and internship postings in the clean_jobs table.

    Use this tool for discovery questions before get_job_details, which retrieves details for
    postings already shown. Pass the user's question with any role, skill, location, or other
    search criteria.
    """
    sql = await generate_sql(question, config)
    validation = validate_sql(sql)

    if not validation.valid:
        logger.warning("query_clean_jobs.sql_rejected", reason=validation.reason)
        return f"Tôi không thể chạy truy vấn đó: {validation.reason}"

    max_rows = load_max_rows()
    bounds = resolve_bounds(validation.sql, max_rows)

    try:
        rows = await asyncio.to_thread(execute_validated_sql, bounds.sql)
    except UndefinedColumnError as exc:
        logger.warning("query_clean_jobs.unknown_column", error=str(exc))
        return render_tool_result(
            QueryToolResult(refusal=QueryRefusal(reason="", glossary_token="ABSENT_FIELD")),
            load_behavior_glossary(),
        )
    except ExecutorError as exc:
        logger.error("query_clean_jobs.db_error", error=str(exc))
        return "Tôi không thể truy xuất dữ liệu do lỗi cơ sở dữ liệu. Vui lòng thử lại sau."

    table = format_rows(rows, bounds.display_cap)
    obligations = filter_enabled_obligations(detect_obligations(validation.sql, table))
    return render_tool_result(
        QueryToolResult(table=table, obligations=obligations),
        load_behavior_glossary(),
    )
