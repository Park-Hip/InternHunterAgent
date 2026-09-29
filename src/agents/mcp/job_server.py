"""Purpose-built FastMCP server for the two read-only job-query tools.

This module owns only the FastMCP server declaration and the two public MCP
wrappers. The wrappers delegate to the framework-neutral implementations in
src/agents/tools so validation, limits, formatting, and error policy stay in a
single place. Public names, descriptions, and the endpoint path are constants
so tests and documentation can assert the compatibility surface directly.
"""

import os

from fastmcp import FastMCP

from src.agents.tools.get_job_details import run_get_job_details
from src.agents.tools.query_clean_jobs import run_query_clean_jobs

# Compatibility surface: these are the stable external names asserted by tests
# and documented for clients. Any rename, new required argument, or changed
# result format requires a new compatibility decision (issue #465).
MCP_SERVER_NAME = "internhunteragent-job-query"
MCP_ENDPOINT_PATH = "/mcp"
QUERY_CLEAN_JOBS_TOOL = "query_clean_jobs"
GET_JOB_DETAILS_TOOL = "get_job_details"

QUERY_CLEAN_JOBS_DESCRIPTION = (
    "Search AI and data job and internship postings in the clean_jobs table. "
    "Use this tool for discovery questions before get_job_details, which "
    "retrieves details for postings already shown. Pass the user's question "
    "with any role, skill, location, or other search criteria."
)
GET_JOB_DETAILS_DESCRIPTION = (
    "Fetch the full description and details for specific job postings by their "
    "id. Use this only when the user asks to know more about, describe, or "
    "compare specific jobs already shown by query_clean_jobs (which lists jobs "
    "with their id). Pass the id values from that list."
)


def create_job_mcp_server() -> FastMCP:
    """Build the job-query MCP server with its two public tools."""
    mcp = FastMCP(MCP_SERVER_NAME)

    @mcp.tool(name=QUERY_CLEAN_JOBS_TOOL, description=QUERY_CLEAN_JOBS_DESCRIPTION)
    async def query_clean_jobs(question: str) -> str:
        """Search clean_jobs postings by the user's natural-language question.

        Args:
            question: The user's question with any role, skill, location, or
                other search criteria.

        Returns:
            Safe Vietnamese results text, cap and caveat honored, or a safety
            refusal string.
        """
        return await run_query_clean_jobs(question)

    @mcp.tool(name=GET_JOB_DETAILS_TOOL, description=GET_JOB_DETAILS_DESCRIPTION)
    async def get_job_details(ids: list[int]) -> str:
        """Fetch full descriptions for the given job-posting ids.

        Args:
            ids: Job-posting ids already shown by query_clean_jobs.

        Returns:
            Safe Vietnamese detail text with the id cap and caveats honored.
        """
        return await run_get_job_details(ids)

    return mcp


def mcp_endpoint_enabled() -> bool:
    """Return whether the Streamable HTTP MCP endpoint should be exposed.

    Defaults to disabled: the endpoint is internal/development-only (issue #465
    access decision, option A) and is not an Internet-facing supported
    integration. Set ``MCP_ENABLED=1`` to reach ``/mcp`` during local manual
    testing; the public Render deployment never sets it.
    """
    return os.getenv("MCP_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
