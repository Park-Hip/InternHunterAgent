"""Concrete serving assembly and the production ASGI entrypoint."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastmcp.utilities.lifespan import combine_lifespans

from src.agents.mcp.adapter import list_job_tools
from src.api.privilege_guard import assert_agent_privileges
from src.agents.mcp.job_server import (
    MCP_ENDPOINT_PATH,
    create_job_mcp_server,
    mcp_endpoint_enabled,
)
from src.agents.runtime.react_agent import AgentRuntime
from src.agents.tracing.langfuse import (
    create_langfuse_stream_observation,
    diagnose_langfuse_startup,
    prepare_native_prompts_startup,
    shutdown_langfuse,
)
from src.api.app import create_app
from src.api.schema_guard import assert_serving_schema
from src.core.checkpointer import build_checkpointer, build_checkpointer_pool
from src.core.config import load_settings

# The shared FastMCP server backs both the in-process agent adapter and, when
# explicitly enabled, the Streamable HTTP endpoint. It is created once at import
# so both surfaces always see the same tools.
_mcp_server = create_job_mcp_server()
# The Streamable HTTP route is registered at the final endpoint path (`/mcp`),
# which app.py adds directly ahead of the static catch-all (a Starlette Mount
# would require a trailing slash).
_mcp_asgi = _mcp_server.http_app(path=MCP_ENDPOINT_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Assemble and tear down dependencies needed by the HTTP service."""
    load_settings()
    await asyncio.to_thread(
        assert_serving_schema
    )  # boot fails loudly on clean_jobs drift
    # Boot also fails loudly when the agent read role cannot read the table, or can
    # write it. A rebuilt table drops the grant, and without this the first user
    # request discovers it instead of the process refusing to start.
    await asyncio.to_thread(assert_agent_privileges)

    pool = build_checkpointer_pool()
    await pool.open()
    diagnostic_task: asyncio.Task[None] | None = None
    try:
        checkpointer = await build_checkpointer(pool)
        await prepare_native_prompts_startup()
        # Tool discovery is awaited exactly once at startup. A failure here
        # raises before app.state.runtime is set, so the service never publishes
        # an agent with a partial tool surface.
        tools = await list_job_tools(_mcp_server)
        app.state.runtime = AgentRuntime(checkpointer=checkpointer, tools=tools)
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


if mcp_endpoint_enabled():
    # The access decision is internal/development-only (issue #465, option A).
    # The combined lifespan enters the MCP session-manager lifespan after the
    # service lifespan and exits it first on shutdown.
    app = create_app(
        lifespan=combine_lifespans(lifespan, _mcp_asgi.lifespan),
        mcp_app=_mcp_asgi,
        mcp_path=MCP_ENDPOINT_PATH,
    )
else:
    app = create_app(lifespan=lifespan)