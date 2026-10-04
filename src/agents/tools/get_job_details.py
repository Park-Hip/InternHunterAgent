"""Framework-neutral implementation of the bounded job-details lookup ability."""

import asyncio

from src.agents.runtime.prompts import load_behavior_glossary
from src.core.config import settings
from src.core.logger import logger
from src.services.query.executor import ExecutorError
from src.services.query.job_details import fetch_job_details
from src.services.query.models import TableArtifact
from src.services.query.obligations import (
    detect_row_obligations,
    filter_enabled_obligations,
)
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


#: Columns kept out of the rendered detail pairs.
#:
#: `id` is a surrogate key within one data load, not a business field. The v0
#: contract permits it for chaining a detail request to a listed posting and
#: forbids describing it as a durable identifier, so echoing it back as one more
#: `column=value` pair teaches the model that a machine column exists on the
#: posting and invites it to repeat the raw key to the reader, which is the
#: `no_schema_identifier_leak` rule in docs/reference/agent-behavior.md.
#:
#: Dropping it from the text costs nothing: the model supplied these ids as the
#: tool argument, and the structured TableArtifact handed to the obligations
#: pass keeps the key, so capping, lookup and chaining are untouched.
_UNRENDERED_COLUMNS = frozenset({"id"})


def _build_answer(ids: list[int], capped_ids: list[int], rows: list[dict]) -> str:
    lines = []
    if len(capped_ids) < len(ids):
        lines.append(
            f"Đang hiển thị thông tin chi tiết của {len(capped_ids)} trong số {len(ids)} tin tuyển dụng được yêu cầu."
        )

    rows_by_id = {row.get("id"): row for row in rows}
    for job_id in capped_ids:
        row = rows_by_id.get(job_id)
        if row is None:
            lines.append(f"Không tìm thấy tin tuyển dụng nào với mã {job_id}.")
            continue
        pairs = ", ".join(
            f"{column}={value}"
            for column, value in row.items()
            if column not in _UNRENDERED_COLUMNS
        )
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


async def run_get_job_details(ids: list[int]) -> str:
    """Return safe Vietnamese job details for the given posting ids."""
    if not ids:
        return (
            "Vui lòng chỉ định mã tin tuyển dụng bạn muốn xem chi tiết hoặc tìm kiếm "
            "trước bằng query_clean_jobs."
        )

    max_detail_ids = load_max_detail_ids()
    capped_ids = ids[:max_detail_ids]

    try:
        rows = await asyncio.to_thread(fetch_job_details, capped_ids)
    except ExecutorError as exc:
        logger.error("get_job_details.db_error", error=str(exc))
        return "Tôi không thể truy xuất dữ liệu do lỗi cơ sở dữ liệu. Vui lòng thử lại sau."

    obligations = filter_enabled_obligations(
        detect_row_obligations(_table_from_detail_rows(rows))
    )
    return render_obligations(
        _build_answer(ids, capped_ids, rows),
        [obligation.glossary_token for obligation in obligations],
        load_behavior_glossary(),
    )