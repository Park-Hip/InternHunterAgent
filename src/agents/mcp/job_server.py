"""Purpose-built FastMCP server for the two read-only job-query tools.

This module owns only the FastMCP server declaration and the two public MCP
wrappers. The wrappers delegate to the framework-neutral implementations in
src/agents/tools so validation, limits, formatting, and error policy stay in a
single place. Public names, descriptions, and the endpoint path are constants
so tests and documentation can assert the compatibility surface directly.
"""

import os

from fastmcp import FastMCP

from src.agents.runtime.prompts import v0_agent_enabled
from src.agents.tools.get_job_details import run_get_job_details
from src.agents.tools.query_clean_jobs import run_query_clean_jobs
from src.agents.tools.v0_query_jobs import TOOL_DESCRIPTION as V0_QUERY_TOOL_DESCRIPTION
from src.agents.tools.v0_query_jobs import run_query_jobs

# Compatibility surface: these are the stable external names asserted by tests
# and documented for clients. Any rename, new required argument, or changed
# result format requires a new compatibility decision (issue #465).
MCP_SERVER_NAME = "internhunteragent-job-query"
MCP_ENDPOINT_PATH = "/mcp"
QUERY_CLEAN_JOBS_TOOL = "query_clean_jobs"
GET_JOB_DETAILS_TOOL = "get_job_details"
V0_QUERY_TOOL = "query_jobs"

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
    """Build the job-query MCP server with one tool pair, never a mixture.

    The v0 bundle registers the governed query tool and nothing else; the v1
    bundle registers the two legacy tools. The choice is the same
    ``agent.agent_v0`` switch the system prompt reads, so the prompt and the
    tool surface cannot disagree.
    """
    mcp = FastMCP(MCP_SERVER_NAME)

    if v0_agent_enabled():
        _register_v0_tools(mcp)
        return mcp

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


def _register_v0_tools(mcp: FastMCP) -> None:
    """Expose the governed query core as the server's only public tool."""

    @mcp.tool(name=V0_QUERY_TOOL, description=V0_QUERY_TOOL_DESCRIPTION)
    def query_jobs(request: dict) -> str:
        """Answer one typed question about the job postings in the database.

        Args:
            request: One typed request. Use shape "list" to show matching
                postings, "count" for a number, "group_count" for a number per
                recorded value, "top_n" for the highest or lowest by one
                recorded field, "aggregate" for a share or a salary figure,
                "compare" for the same number across two conditions, and
                "detail" for postings whose ids you already showed. Filters may
                use role, technology, location, job_level, company, title,
                is_internship, salary_currency, salary_min, salary_max,
                has_link, and free_text.

        Returns:
            The applied criteria, the full match count, the rows, and the
            caveats the answer must carry. A refusal comes back as UNSUPPORTED
            or AMBIGUOUS with a reason, never as a number.
        """
        return run_query_jobs(request)

    return None


def mcp_endpoint_enabled() -> bool:
    """Return whether the Streamable HTTP MCP endpoint should be exposed.

    Defaults to disabled: the endpoint is internal/development-only (issue #465
    access decision, option A) and is not an Internet-facing supported
    integration. Set ``MCP_ENABLED=1`` to reach ``/mcp`` during local manual
    testing; the public Render deployment never sets it.
    """
    return os.getenv("MCP_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
