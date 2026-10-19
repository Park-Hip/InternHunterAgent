"""Framework-neutral implementation of the bounded job-details lookup ability.

The tool returns typed facts or raises ``ToolFailure``; no user-facing sentence
is written here (#702). The system prompt owns all wording.
"""

import asyncio

from src.agents.tools.failures import ToolFailure
from src.core.config import settings
from src.core.logger import logger
from src.services.query.executor import (
    ExecutorError,
    QueryTimeoutError,
    ResultTooLargeError,
    UndefinedColumnError,
)
from src.services.query.job_details import fetch_job_details
from src.services.query.models import JobDetailsResult
from src.services.query.table_formatter import json_value


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


def _unique_ids(ids: list[int]) -> list[int]:
    """Drop duplicate ids, keeping the first occurrence of each."""
    return list(dict.fromkeys(ids))


async def run_get_job_details(ids: list[int]) -> JobDetailsResult:
    """Fetch full posting details for the given posting ids as typed facts."""
    max_detail_ids = load_max_detail_ids()
    unique_ids = _unique_ids(ids)
    fetched_ids = unique_ids[:max_detail_ids]
    not_fetched = unique_ids[max_detail_ids:]

    try:
        rows = await asyncio.to_thread(fetch_job_details, fetched_ids)
    except UndefinedColumnError as exc:
        logger.warning("get_job_details.unknown_column", error=str(exc))
        raise ToolFailure("unknown_column", exc.message_primary) from exc
    except QueryTimeoutError as exc:
        logger.warning("get_job_details.timeout", error=str(exc))
        raise ToolFailure(
            "timeout", f"statement exceeded the {exc.timeout_ms} ms limit"
        ) from exc
    except ResultTooLargeError as exc:
        logger.warning("get_job_details.too_large", error=str(exc))
        raise ToolFailure(
            "too_large", "result exceeds the byte budget; select fewer columns"
        ) from exc
    except ExecutorError as exc:
        logger.error("get_job_details.db_error", error=str(exc))
        raise ToolFailure("unavailable", "the database could not run the query") from exc

    rows_by_id = {row.get("id"): row for row in rows}
    jobs = [
        {column: json_value(value) for column, value in rows_by_id[job_id].items()}
        for job_id in fetched_ids
        if job_id in rows_by_id
    ]
    not_found = [job_id for job_id in fetched_ids if job_id not in rows_by_id]
    return JobDetailsResult(jobs=jobs, not_found=not_found, not_fetched=not_fetched)
