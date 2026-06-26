import asyncio

from langchain.messages import HumanMessage
from langchain.tools import tool

from src.agents.runtime.prompts import load_schema_context, load_sql_generation_prompt
from src.agents.runtime.provider import AgentProvider
from src.services.query.executor import ExecutorError, execute_validated_sql
from src.services.query.models import TableArtifact
from src.services.query.sql_validator import validate_sql
from src.services.query.table_formatter import format_rows


def generate_sql(question: str) -> str:
    schema_context = load_schema_context()
    sql_generation_prompt = load_sql_generation_prompt()
    model = AgentProvider().build_model()

    response = model.invoke(
        [HumanMessage(content=f"{sql_generation_prompt}\n\n{schema_context}\n\nQuestion: {question}")]
    )
    return response.content.strip()


def _build_answer(table: TableArtifact) -> str:
    if table.row_count == 0:
        return "No matching internship job postings were found."

    lines = [f"Found {table.row_count} result(s) with columns: {', '.join(table.columns)}."]
    for row in table.rows:
        pairs = ", ".join(f"{column}={value}" for column, value in zip(table.columns, row))
        lines.append(f"- {pairs}")
    return "\n".join(lines)


@tool
async def query_clean_jobs(question: str) -> str:
    """Answer questions about internship job postings stored in the clean_jobs table."""
    sql = generate_sql(question)
    validation = validate_sql(sql)

    if not validation.valid:
        return f"I can't run that query: {validation.reason}"

    try:
        rows = await asyncio.to_thread(execute_validated_sql, validation.sql)
    except ExecutorError:
        return "I couldn't retrieve the requested data due to a database error. Please try again later."

    table = format_rows(rows)
    return _build_answer(table)
