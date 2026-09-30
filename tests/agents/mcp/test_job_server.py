from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastmcp import Client

from src.agents.mcp.job_server import (
    GET_JOB_DETAILS_DESCRIPTION,
    GET_JOB_DETAILS_TOOL,
    MCP_SERVER_NAME,
    QUERY_CLEAN_JOBS_DESCRIPTION,
    QUERY_CLEAN_JOBS_TOOL,
    create_job_mcp_server,
)
from tests.agents.v0_switch import agent_v0


def _text_of(result) -> str:
    return "".join(str(block.text) for block in result.content)


class JobMcpServerContractTests(unittest.IsolatedAsyncioTestCase):
    """The v1 tool pair, which the cutover unregisters but does not delete."""
    def test_tool_descriptions_are_pinned_compatibility_surface(self) -> None:
        self.assertEqual(
            QUERY_CLEAN_JOBS_DESCRIPTION,
            "Search AI and data job and internship postings in the clean_jobs table. "
            "Use this tool for discovery questions before get_job_details, which "
            "retrieves details for postings already shown. Pass the user's question "
            "with any role, skill, location, or other search criteria.",
        )
        self.assertEqual(
            GET_JOB_DETAILS_DESCRIPTION,
            "Fetch the full description and details for specific job postings by their "
            "id. Use this only when the user asks to know more about, describe, or "
            "compare specific jobs already shown by query_clean_jobs (which lists jobs "
            "with their id). Pass the id values from that list.",
        )

    async def test_server_name_and_tool_surface(self) -> None:
        with agent_v0(False):
            await self._test_server_name_and_tool_surface()

    async def _test_server_name_and_tool_surface(self) -> None:
        mcp = create_job_mcp_server()
        self.assertEqual(mcp.name, MCP_SERVER_NAME)

        async with Client(mcp) as client:
            tools = await client.list_tools()

        self.assertEqual(sorted(tool.name for tool in tools), sorted([
            QUERY_CLEAN_JOBS_TOOL,
            GET_JOB_DETAILS_TOOL,
        ]))
        by_name = {tool.name: tool for tool in tools}
        self.assertEqual(
            by_name[QUERY_CLEAN_JOBS_TOOL].description, QUERY_CLEAN_JOBS_DESCRIPTION
        )
        self.assertEqual(
            by_name[GET_JOB_DETAILS_TOOL].description, GET_JOB_DETAILS_DESCRIPTION
        )

    async def test_input_schemas_mark_required_arguments(self) -> None:
        with agent_v0(False):
            await self._test_input_schemas_mark_required_arguments()

    async def _test_input_schemas_mark_required_arguments(self) -> None:
        async with Client(create_job_mcp_server()) as client:
            tools = await client.list_tools()

        by_name = {tool.name: tool.input_schema for tool in tools}
        question_schema = by_name[QUERY_CLEAN_JOBS_TOOL]
        self.assertEqual(question_schema["type"], "object")
        self.assertEqual(question_schema["properties"]["question"]["type"], "string")
        self.assertEqual(question_schema["required"], ["question"])

        ids_schema = by_name[GET_JOB_DETAILS_TOOL]
        self.assertEqual(ids_schema["type"], "object")
        self.assertEqual(ids_schema["properties"]["ids"]["type"], "array")
        self.assertEqual(
            ids_schema["properties"]["ids"]["items"]["type"], "integer"
        )
        self.assertEqual(ids_schema["required"], ["ids"])

    async def test_query_clean_jobs_invokes_behavior_with_question(self) -> None:
        with agent_v0(False):
            await self._test_query_clean_jobs_invokes_behavior_with_question()

    async def _test_query_clean_jobs_invokes_behavior_with_question(self) -> None:
        mcp = create_job_mcp_server()
        behavior = AsyncMock(return_value="Tìm thấy 2 kết quả")
        with patch("src.agents.mcp.job_server.run_query_clean_jobs", behavior):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    QUERY_CLEAN_JOBS_TOOL, {"question": "data analyst intern"}
                )

        behavior.assert_awaited_once_with("data analyst intern")
        self.assertEqual(_text_of(result), "Tìm thấy 2 kết quả")

    async def test_get_job_details_invokes_behavior_with_ids(self) -> None:
        with agent_v0(False):
            await self._test_get_job_details_invokes_behavior_with_ids()

    async def _test_get_job_details_invokes_behavior_with_ids(self) -> None:
        mcp = create_job_mcp_server()
        behavior = AsyncMock(return_value="Chi tiết tin tuyển dụng")
        with patch("src.agents.mcp.job_server.run_get_job_details", behavior):
            async with Client(mcp) as client:
                result = await client.call_tool(GET_JOB_DETAILS_TOOL, {"ids": [1, 2]})

        behavior.assert_awaited_once_with([1, 2])
        self.assertEqual(_text_of(result), "Chi tiết tin tuyển dụng")

    async def test_invalid_arguments_never_reach_behavior(self) -> None:
        mcp = create_job_mcp_server()
        query_behavior = AsyncMock(return_value="x")
        details_behavior = AsyncMock(return_value="y")
        with (
            patch("src.agents.mcp.job_server.run_query_clean_jobs", query_behavior),
            patch("src.agents.mcp.job_server.run_get_job_details", details_behavior),
        ):
            async with Client(mcp) as client:
                with self.assertRaises(Exception):
                    await client.call_tool(GET_JOB_DETAILS_TOOL, {"ids": ["not-an-int"]})
                with self.assertRaises(Exception):
                    await client.call_tool(QUERY_CLEAN_JOBS_TOOL, {"question": 42})

        query_behavior.assert_not_called()
        details_behavior.assert_not_called()


if __name__ == "__main__":
    unittest.main()