from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import query, health
from src.agents.runtime.factory import agent_factory
from src.agents.runtime.react_agent import AgentRuntime
from src.core.checkpointer import build_checkpointer, build_checkpointer_pool
from src.core.config import load_settings, settings


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


def create_app(*, cors_config: dict[str, Any] | None = None) -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    resolved_cors = cors_config or _load_cors_config()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_cors["allowed_origins"],
        allow_credentials=resolved_cors["allow_credentials"],
        allow_methods=resolved_cors["allowed_methods"],
        allow_headers=resolved_cors["allowed_headers"],
    )

    app.include_router(query.router, prefix="/api/v1")
    app.include_router(health.router, prefix="/api/v1")
    return app


app = create_app()
