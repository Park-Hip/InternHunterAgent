"""Concrete serving assembly and the production ASGI entrypoint."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from src.core.config import load_settings

# Configuration is the import-time contract (#640). The imports below read
# settings while they run, so loading here first makes the refusal explicit
# instead of accidental: a missing DATABASE_URL or AGENT_DATABASE_URL, bad YAML,
# or an invalid agent section raises ConfigLoadError and uvicorn exits 1 before
# the MCP server, the app object, or the lifespan exists, and before LangChain,
# LiteLLM, and FastMCP are imported. The lifespan therefore trusts the cached
# settings and never reloads them.
load_settings()

# The remaining imports follow the configuration load on purpose, so the
# expensive ones below cannot run before a bad configuration has refused boot.
# E402 is waived for this module in pyproject.toml.
from fastapi import FastAPI
from fastmcp.utilities.lifespan import combine_lifespans
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.agents.mcp.adapter import list_job_tools
from src.agents.mcp.job_server import (
    MCP_ENDPOINT_PATH,
    create_job_mcp_server,
    mcp_endpoint_enabled,
)
from src.agents.runtime.provider import assert_profile_credential
from src.agents.runtime.react_agent import AgentRuntime
from src.agents.tracing.langfuse import (
    create_langfuse_stream_observation,
    diagnose_langfuse_startup,
    init_langfuse,
    prepare_native_prompts_startup,
    shutdown_langfuse,
)
from src.api.app import create_app
from src.api.privilege_guard import assert_agent_privileges
from src.api.schema_guard import assert_serving_schema
from src.core.checkpointer import (
    build_checkpointer,
    build_checkpointer_pool,
    delete_stale_threads,
)
from src.core.config import settings
from src.core.logger import logger

# The shared FastMCP server backs both the in-process agent adapter and, when
# explicitly enabled, the Streamable HTTP endpoint. It is created once at import
# so both surfaces always see the same tools.
_mcp_server = create_job_mcp_server()
# The Streamable HTTP route is registered at the final endpoint path (`/mcp`),
# which app.py adds directly ahead of the static catch-all (a Starlette Mount
# would require a trailing slash).
_mcp_asgi = _mcp_server.http_app(path=MCP_ENDPOINT_PATH)


def _served_profiles() -> tuple[str, ...]:
    """The profiles the served tool surface can invoke, in refusal order.

    The react loop is always reachable, and the nested sql_generation call is
    reachable because the query_clean_jobs tool always registers the SQL path.
    """
    return ("react", "sql_generation")


def _assert_served_profile_credentials() -> None:
    """Refuse to serve when a served profile's deployment has no usable key.

    Without this, a deploy whose selected provider key is missing boots green
    and fails every question; refusing here turns that into a failed deploy
    that names the variable. Deployments no served profile selects stay
    optional, so a checkout needs only the selected provider's key.
    """
    profiles = _served_profiles()
    for profile in profiles:
        assert_profile_credential(profile)
    logger.info("api.provider_credentials_ok", profiles=list(profiles))


# The retention sweep's cadence. The configured age is measured in days, so the
# sweep runs daily; a sleeping Render instance sweeps when it next boots (#673).
_RETENTION_SWEEP_INTERVAL_SECONDS = 24 * 60 * 60


async def _sweep_checkpoint_threads(checkpointer: AsyncPostgresSaver) -> None:
    """Delete stale conversation threads once now, then once a day.

    A failed sweep is logged and the loop continues: retention is housekeeping,
    so a database hiccup must not silently end it for the process's lifetime.
    """
    while True:
        try:
            deleted = await delete_stale_threads(
                checkpointer, retention_days=settings.agent.retention_days
            )
            logger.info(
                "checkpointer.retention_swept",
                deleted_threads=len(deleted),
                retention_days=settings.agent.retention_days,
            )
        except Exception:
            logger.exception("checkpointer.retention_sweep_failed")
        await asyncio.sleep(_RETENTION_SWEEP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Assemble and tear down dependencies needed by the HTTP service."""
    await asyncio.to_thread(
        assert_serving_schema
    )  # boot fails loudly on clean_jobs drift
    # Boot also fails loudly when the agent read role cannot read the table, or can
    # write it. A rebuilt table drops the grant, and without this the first user
    # request discovers it instead of the process refusing to start.
    await asyncio.to_thread(assert_agent_privileges)
    # Boot also fails loudly when a deployment a served profile selects has no
    # key. Without this the process serves 500s on every question; the check
    # runs before the pool opens, so a refusal leaves nothing to tear down.
    _assert_served_profile_credentials()

    pool = build_checkpointer_pool()
    await pool.open()
    diagnostic_task: asyncio.Task[None] | None = None
    retention_task: asyncio.Task[None] | None = None
    try:
        # Both ends of the Langfuse client's life are here: created after the
        # guards and before prompt warming so the registry resolves against it,
        # drained by the matching shutdown in the finally chain below. The call
        # is local and never raises, so boot does not wait on Langfuse.
        init_langfuse()
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
        # Fire-and-track: retention is housekeeping too, so boot does not wait
        # for the sweep. It sweeps once now, then daily (#673).
        retention_task = asyncio.create_task(_sweep_checkpoint_threads(checkpointer))
        yield
    finally:
        try:
            # Both background tasks stop before the pool they use closes; each
            # step runs even if an earlier one raised.
            for task in (diagnostic_task, retention_task):
                if task is not None and not task.done():
                    task.cancel()
            for task in (diagnostic_task, retention_task):
                if task is None:
                    continue
                try:
                    await task
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
