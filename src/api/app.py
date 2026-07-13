from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.api.routes import query, health
from src.agents.runtime.factory import agent_factory
from src.agents.runtime.react_agent import AgentRuntime
from src.core.checkpointer import build_checkpointer, build_checkpointer_pool
from src.core.config import load_settings, settings
from src.core.errors import BUSY_MESSAGE


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_settings()

    pool = build_checkpointer_pool()
    await pool.open()
    try:
        checkpointer = await build_checkpointer(pool)
        app.state.runtime = AgentRuntime(agent=agent_factory(checkpointer=checkpointer))
        yield
    finally:
        await pool.close()


def _load_cors_config() -> dict[str, Any]:
    api_cfg = settings.config_yaml.get("api")
    if not isinstance(api_cfg, dict):
        api_cfg = {}

    cors_cfg = api_cfg.get("cors")
    if not isinstance(cors_cfg, dict):
        cors_cfg = {}

    return {
        "allowed_origins": cors_cfg.get("allowed_origins", []),
        "allow_credentials": cors_cfg.get("allow_credentials", False),
        "allowed_methods": cors_cfg.get("allowed_methods", ["GET", "POST", "OPTIONS"]),
        "allowed_headers": cors_cfg.get("allowed_headers", ["*"]),
    }


def _load_rate_limit() -> str:
    api_cfg = settings.config_yaml.get("api")
    if not isinstance(api_cfg, dict):
        return "15/minute"

    rate_limit = api_cfg.get("rate_limit", "15/minute")
    if not isinstance(rate_limit, str) or not rate_limit.strip():
        return "15/minute"

    return rate_limit


def _load_docs_enabled() -> bool:
    api_cfg = settings.config_yaml.get("api")
    if not isinstance(api_cfg, dict):
        return True

    docs_enabled = api_cfg.get("docs_enabled", True)
    if not isinstance(docs_enabled, bool):
        return True

    return docs_enabled


async def _rate_limit_exceeded_handler(request, exc):
    return JSONResponse(status_code=429, content={"detail": BUSY_MESSAGE})


def create_app(
    *,
    cors_config: dict[str, Any] | None = None,
    rate_limit: str | None = None,
    docs_enabled: bool | None = None,
) -> FastAPI:
    resolved_docs_enabled = (
        _load_docs_enabled() if docs_enabled is None else docs_enabled
    )
    app = FastAPI(
        lifespan=lifespan,
        docs_url="/docs" if resolved_docs_enabled else None,
        redoc_url="/redoc" if resolved_docs_enabled else None,
        openapi_url="/openapi.json" if resolved_docs_enabled else None,
    )

    resolved_cors = cors_config or _load_cors_config()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_cors["allowed_origins"],
        allow_credentials=resolved_cors["allow_credentials"],
        allow_methods=resolved_cors["allowed_methods"],
        allow_headers=resolved_cors["allowed_headers"],
    )

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    resolved_rate_limit = rate_limit or _load_rate_limit()
    app.include_router(
        query.create_router(limiter=limiter, rate_limit=resolved_rate_limit),
        prefix="/api/v1",
    )
    app.include_router(health.router, prefix="/api/v1")
    return app


app = create_app()
