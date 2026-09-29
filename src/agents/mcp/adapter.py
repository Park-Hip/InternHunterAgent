"""In-process LangChain tool discovery for the job-query MCP server."""

from langchain.mcp import MCPAdapter
from langchain_core.tools import BaseTool


async def list_job_tools(mcp_target) -> list[BaseTool]:
    """Discover the job-query MCP tools as LangChain tools.

    The target is composed in by the caller; production passes the in-process
    FastMCP server directly so there is no loopback socket or URL. Discovery is
    awaited exactly once at lifespan startup, and a failure here raises so the
    application never publishes an agent with a partial tool surface.
    """
    async with MCPAdapter(mcp_target) as adapter:
        return await adapter.list_tools()