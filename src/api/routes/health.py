import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.core.config import settings
from src.core.db import session_factory

router = APIRouter()


@router.get("/health")
async def health_check():
    status_code = 200
    health_status = {"api": "online"}

    return {
        "health_status": health_status,
        "status_code": status_code
    }


def get_data_snapshot_date() -> str:
    api_cfg = settings.config_yaml.get("api")
    if not isinstance(api_cfg, dict):
        return ""
    demo_cfg = api_cfg.get("demo")
    if not isinstance(demo_cfg, dict):
        return ""
    # Future daily ingestion: replace this with SELECT MAX(fetched_at); endpoint/UI stay unchanged.
    return str(demo_cfg.get("data_snapshot_date", ""))


def _select_one() -> None:
    with session_factory() as session:
        session.execute(text("SELECT 1"))


@router.get("/ready")
async def readiness_check():
    try:
        await asyncio.to_thread(_select_one)
    except Exception:
        return JSONResponse(status_code=503, content={"status": "error"})
    return {"status": "ok", "data_snapshot_date": get_data_snapshot_date()}
