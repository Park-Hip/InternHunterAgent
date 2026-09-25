"""Concrete serving assembly and the production ASGI entrypoint."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.agents.runtime.factory import agent_factory
from src.agents.runtime.react_agent import AgentRuntime
from src.agents.tracing.langfuse import (
    create_langfuse_stream_observation,
    diagnose_langfuse_startup,
    shutdown_langfuse,
)
from src.api.app import create_app
from src.api.schema_guard import assert_serving_schema
from src.core.checkpointer import build_checkpointer, build_checkpointer_pool
from src.core.config import load_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Assemble and tear down dependencies needed by the HTTP service."""
    load_settings()
    await asyncio.to_thread(assert_serving_schema)  # boot fails loudly on clean_jobs drift

    pool = build_checkpointer_pool()
    await pool.open()
    diagnostic_task: asyncio.Task[None] | None = None
    try:
        checkpointer = await build_checkpointer(pool)
        app.state.runtime = AgentRuntime(agent=agent_factory(checkpointer=checkpointer))
        app.state.stream_observation_factory = create_langfuse_stream_observation
        # Fire-and-track: this is a non-fatal diagnostic, so boot does not wait for
        # a network round trip to Langfuse.
        diagnostic_task = asyncio.create_task(diagnose_langfuse_startup())
        yield
    finally:
        try:
            if diagnostic_task is not None:
                if not diagnostic_task.done():
                    diagnostic_task.cancel()
                try:
                    await diagnostic_task
                except asyncio.CancelledError:
                    pass
        finally:
            try:
                await shutdown_langfuse()
            finally:
                await pool.close()


app = create_app(lifespan=lifespan)
