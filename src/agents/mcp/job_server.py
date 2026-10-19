"""Purpose-built FastMCP server for the two read-only job-query tools.

This module owns the FastMCP server declaration, the two public MCP wrappers,
and the model-facing tool and argument descriptions. The wrappers delegate to
the framework-neutral implementations in src/agents/tools, so validation,
limits, fact shaping, and the failure vocabulary stay in a single place.

Results are typed JSON (a Pydantic model per tool), so FastMCP publishes an
``outputSchema`` and the LangChain adapter keeps the structured content as the
tool message artifact. Every failure the behaviors raise reaches the model as
a ``ToolError``, which the adapter turns into a ``status="error"`` tool
message (#702, E4).

Public names, descriptions, argument names, and the endpoint path are the
compatibility surface asserted by tests. The argument rename from ``question``
to ``request`` and the switch from rendered text to typed JSON are the
compatibility decision this issue owns (#465).
"""

import os
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from src.agents.tools.failures import ToolFailure
from src.agents.tools.get_job_details import load_max_detail_ids, run_get_job_details
from src.agents.tools.query_clean_jobs import run_query_clean_jobs
from src.services.query.models import JobDetailsResult, QueryResult

# Compatibility surface: these are the stable external names asserted by tests
# and documented for clients. Any rename, new required argument, or changed
# result format requires a new compatibility decision (issue #465).
MCP_SERVER_NAME = "internhunteragent-job-query"
MCP_ENDPOINT_PATH = "/mcp"
QUERY_CLEAN_JOBS_TOOL = "query_clean_jobs"
GET_JOB_DETAILS_TOOL = "get_job_details"

QUERY_CLEAN_JOBS_DESCRIPTION = (
    "Search, count, or summarize AI and data job postings with one read-only "
    "SQL query. Pass `request`: one standalone request that restates every "
    "filter from earlier turns that still applies. Returns JSON: `sql` (the "
    "query that ran; internal, never shown to the user), `columns`, `rows`, "
    "`row_count` (rows returned), and `total_rows` (rows the query matches "
    "without any LIMIT). A count or summary returns its figures in `rows`."
)
REQUEST_ARGUMENT_DESCRIPTION = (
    "One standalone request in the user's language that restates every filter "
    "from earlier turns that still applies."
)
#: ``{max_detail_ids}`` is filled from ``agent.query.max_detail_ids`` so the
#: description cannot drift from the configured cap.
GET_JOB_DETAILS_DESCRIPTION = (
    "Fetch full details, including the description, for up to "
    "{max_detail_ids} postings by id from an earlier query_clean_jobs result. "
    "Returns JSON: `jobs` (in request order), `not_found` (ids with no "
    "posting), and `not_fetched` (ids over the cap; call again for them)."
)
IDS_ARGUMENT_DESCRIPTION = "Posting ids from an earlier query_clean_jobs result."


def job_details_description() -> str:
    """The ``get_job_details`` description with the configured id cap filled."""
    return GET_JOB_DETAILS_DESCRIPTION.format(max_detail_ids=load_max_detail_ids())


def create_job_mcp_server() -> FastMCP:
    """Build the job-query MCP server with the v1 tool pair."""
    mcp = FastMCP(MCP_SERVER_NAME)

    @mcp.tool(name=QUERY_CLEAN_JOBS_TOOL, description=QUERY_CLEAN_JOBS_DESCRIPTION)
    async def query_clean_jobs(
        request: Annotated[str, Field(description=REQUEST_ARGUMENT_DESCRIPTION)],
    ) -> QueryResult:
        try:
            return await run_query_clean_jobs(request)
        except ToolFailure as failure:
            raise ToolError(f"{failure.kind}: {failure.detail}") from failure

    @mcp.tool(name=GET_JOB_DETAILS_TOOL, description=job_details_description())
    async def get_job_details(
        ids: Annotated[
            list[int],
            Field(min_length=1, description=IDS_ARGUMENT_DESCRIPTION),
        ],
    ) -> JobDetailsResult:
        try:
            return await run_get_job_details(ids)
        except ToolFailure as failure:
            raise ToolError(f"{failure.kind}: {failure.detail}") from failure

    return mcp


def mcp_endpoint_enabled() -> bool:
    """Return whether the Streamable HTTP MCP endpoint should be exposed.

    Defaults to disabled: the endpoint is internal/development-only (issue #465
    access decision, option A) and is not an Internet-facing supported
    integration. Set ``MCP_ENABLED=1`` to reach ``/mcp`` during local manual
    testing; the public Render deployment never sets it.
    """
    return os.getenv("MCP_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
