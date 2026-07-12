from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import query, health
from src.agents.runtime.factory import agent_factory
from src.agents.runtime.react_agent import AgentRuntime
from src.core.checkpointer import build_checkpointer, build_checkpointer_pool
from src.core.config import load_settings


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


app = FastAPI(lifespan=lifespan)

app.include_router(query.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
