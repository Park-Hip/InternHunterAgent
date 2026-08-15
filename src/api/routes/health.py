import asyncio
from datetime import date

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.core.config import settings
from src.core.db import session_factory
from src.core.logger import logger

router = APIRouter()


@router.get("/health")
async def health_check():
    status_code = 200
    health_status = {"api": "online"}

    return {
        "health_status": health_status,
        "status_code": status_code
    }


def _configured_snapshot_date() -> str:
    """Static fallback from config/settings.yaml; "" when the shape is malformed."""
    api_cfg = settings.config_yaml.get("api")
    if not isinstance(api_cfg, dict):
        return ""
    demo_cfg = api_cfg.get("demo")
    if not isinstance(demo_cfg, dict):
        return ""
    return str(demo_cfg.get("data_snapshot_date", ""))


def _select_max_last_seen() -> date | None:
    with session_factory() as session:
        result = session.execute(text("SELECT MAX(last_seen_at)::date FROM clean_jobs"))
        return result.scalar()


def get_data_snapshot_date() -> tuple[str, str]:
    """Return the refresh date and whether it was measured or configured."""
    try:
        max_last_seen = _select_max_last_seen()
    except Exception:
        logger.warning("snapshot_date_query_failed_using_config_fallback", exc_info=True)
        return _configured_snapshot_date(), "configured_fallback"
    if max_last_seen is None:
        logger.info("snapshot_date_empty_table_using_config_fallback")
        return _configured_snapshot_date(), "configured_fallback"
    return max_last_seen.isoformat(), "measured"


def _select_one() -> None:
    with session_factory() as session:
        session.execute(text("SELECT 1"))


@router.get("/ready")
async def readiness_check():
    try:
        await asyncio.to_thread(_select_one)
    except Exception:
        return JSONResponse(status_code=503, content={"status": "error"})
    snapshot_date, snapshot_date_provenance = await asyncio.to_thread(get_data_snapshot_date)
    return {
        "status": "ok",
        "data_snapshot_date": snapshot_date,
        "data_snapshot_date_provenance": snapshot_date_provenance,
    }
