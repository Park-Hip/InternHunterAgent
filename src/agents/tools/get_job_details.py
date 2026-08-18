import asyncio

from langchain.tools import tool

from src.agents.runtime.prompts import load_behavior_glossary
from src.core.config import settings
from src.core.logger import logger
from src.services.query.executor import ExecutorError
from src.services.query.job_details import fetch_job_details
from src.services.query.models import TableArtifact
from src.services.query.obligations import detect_row_obligations, filter_enabled_obligations
from src.services.query.table_formatter import render_obligations


def load_max_detail_ids() -> int:
    agent_cfg = settings.config_yaml.get("agent")
    if not isinstance(agent_cfg, dict):
        raise ValueError("Missing 'agent' section in config/settings.yaml")

    query_cfg = agent_cfg.get("query")
    if not isinstance(query_cfg, dict):
        raise ValueError("Missing 'agent.query' section in config/settings.yaml")

    max_detail_ids = query_cfg.get("max_detail_ids")
    if (
        isinstance(max_detail_ids, bool)
        or not isinstance(max_detail_ids, int)
        or max_detail_ids <= 0
    ):
        raise ValueError(
            "agent.query.max_detail_ids must be a positive integer in config/settings.yaml"
        )

    return max_detail_ids


def _build_answer(ids: list[int], capped_ids: list[int], rows: list[dict]) -> str:
    lines = []
    if len(capped_ids) < len(ids):
        lines.append(f"Showing details for {len(capped_ids)} of {len(ids)} requested.")

    rows_by_id = {row.get("id"): row for row in rows}
    for job_id in capped_ids:
        row = rows_by_id.get(job_id)
        if row is None:
            lines.append(f"No posting found for id {job_id}.")
            continue
        pairs = ", ".join(f"{column}={value}" for column, value in row.items())
        lines.append(f"- {pairs}")

    return "\n".join(lines)


def _table_from_detail_rows(rows: list[dict]) -> TableArtifact:
    if not rows:
        return TableArtifact(columns=[], rows=[], row_count=0)
    columns = list(rows[0])
    return TableArtifact(
        columns=columns,
        rows=[[row.get(column) for column in columns] for row in rows],
        row_count=len(rows),
    )


@tool
async def get_job_details(ids: list[int]) -> str:
    """Fetch the full description and details for specific job postings by their id. Use this only when the user asks to know more about, describe, or compare specific jobs already shown by query_clean_jobs (which lists jobs with their id). Pass the id values from that list."""
    if not ids:
        return (
            "Please specify which job's id you'd like details for, or run a search "
            "with query_clean_jobs first."
        )

    max_detail_ids = load_max_detail_ids()
    capped_ids = ids[:max_detail_ids]

    try:
        rows = await asyncio.to_thread(fetch_job_details, capped_ids)
    except ExecutorError as exc:
        logger.error("get_job_details.db_error", error=str(exc))
        return "I couldn't retrieve the requested data due to a database error. Please try again later."

    obligations = filter_enabled_obligations(detect_row_obligations(_table_from_detail_rows(rows)))
    return render_obligations(
        _build_answer(ids, capped_ids, rows),
        [obligation.glossary_token for obligation in obligations],
        load_behavior_glossary(),
    )
