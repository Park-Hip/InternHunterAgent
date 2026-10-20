"""Contract tests for the two MCP tool wrappers (#702).

The public names, descriptions, argument names, input schemas, output schemas,
and typed JSON results are the compatibility surface (#465). Every case here is
in-process: no model call, no database, and the behaviors are replaced.
"""

from __future__ import annotations

import logging
import unittest
from unittest.mock import AsyncMock, patch

from fastmcp import Client
from fastmcp.exceptions import ToolError

from src.agents.mcp.job_server import (
    GET_JOB_DETAILS_TOOL,
    IDS_ARGUMENT_DESCRIPTION,
    MCP_SERVER_NAME,
    QUERY_CLEAN_JOBS_DESCRIPTION,
    QUERY_CLEAN_JOBS_TOOL,
    REQUEST_ARGUMENT_DESCRIPTION,
    create_job_mcp_server,
    job_details_description,
    to_tool_error,
)
from src.agents.tools.failures import ToolFailure
from src.agents.tools.get_job_details import load_max_detail_ids
from src.services.query.models import JobDetailsResult, QueryResult


def _text_of(result) -> str:
    return "".join(str(block.text) for block in result.content)


class JobMcpServerContractTests(unittest.IsolatedAsyncioTestCase):
    """The tool pair the agent reaches through the in-process adapter."""

    def test_tool_descriptions_are_pinned_compatibility_surface(self) -> None:
        self.assertEqual(
            QUERY_CLEAN_JOBS_DESCRIPTION,
            "Search, count, or summarize AI and data job postings with one read-only "
            "SQL query. Pass `request`: one standalone request that restates every "
            "filter from earlier turns that still applies. Returns JSON: `sql` (the "
            "query that ran; internal, never shown to the user), `columns`, `rows`, "
            "`row_count` (rows returned), and `total_rows` (rows the query matches "
            "without any LIMIT or OFFSET). A count or summary returns its figures in "
            "`rows`.",
        )
        self.assertEqual(
            REQUEST_ARGUMENT_DESCRIPTION,
            "One standalone request in the user's language that restates every filter "
            "from earlier turns that still applies.",
        )
        self.assertEqual(
            IDS_ARGUMENT_DESCRIPTION,
            "Posting ids from an earlier query_clean_jobs result.",
        )

    def test_the_details_description_names_the_configured_id_cap(self) -> None:
        self.assertEqual(
            job_details_description(),
            "Fetch full details, including the description, for up to "
            f"{load_max_detail_ids()} postings by id from an earlier query_clean_jobs "
            "result. Returns JSON: `jobs` (in request order), `not_found` (ids with no "
            "posting), and `not_fetched` (ids over the cap; call again for them).",
        )

    async def test_server_name_tool_surface_and_input_schemas(self) -> None:
        mcp = create_job_mcp_server()
        self.assertEqual(mcp.name, MCP_SERVER_NAME)

        async with Client(mcp) as client:
            tools = await client.list_tools()

        self.assertEqual(
            sorted(tool.name for tool in tools),
            [GET_JOB_DETAILS_TOOL, QUERY_CLEAN_JOBS_TOOL],
        )
        by_name = {tool.name: tool for tool in tools}
        self.assertEqual(
            by_name[QUERY_CLEAN_JOBS_TOOL].description, QUERY_CLEAN_JOBS_DESCRIPTION
        )
        self.assertEqual(
            by_name[GET_JOB_DETAILS_TOOL].description, job_details_description()
        )

        request_schema = by_name[QUERY_CLEAN_JOBS_TOOL].input_schema
        self.assertEqual(request_schema["type"], "object")
        self.assertEqual(request_schema["properties"]["request"]["type"], "string")
        self.assertEqual(
            request_schema["properties"]["request"]["description"],
            REQUEST_ARGUMENT_DESCRIPTION,
        )
        self.assertEqual(request_schema["required"], ["request"])

        ids_schema = by_name[GET_JOB_DETAILS_TOOL].input_schema
        self.assertEqual(ids_schema["type"], "object")
        self.assertEqual(ids_schema["properties"]["ids"]["type"], "array")
        self.assertEqual(ids_schema["properties"]["ids"]["items"]["type"], "integer")
        self.assertEqual(
            ids_schema["properties"]["ids"]["description"], IDS_ARGUMENT_DESCRIPTION
        )
        self.assertEqual(ids_schema["properties"]["ids"]["minItems"], 1)
        self.assertEqual(ids_schema["required"], ["ids"])

    async def test_both_tools_publish_a_typed_output_schema(self) -> None:
        async with Client(create_job_mcp_server()) as client:
            by_name = {tool.name: tool for tool in await client.list_tools()}

        query_schema = by_name[QUERY_CLEAN_JOBS_TOOL].output_schema
        self.assertEqual(
            sorted(query_schema["properties"]),
            ["columns", "row_count", "rows", "sql", "total_rows"],
        )
        self.assertEqual(
            sorted(query_schema["required"]),
            ["columns", "row_count", "rows", "sql", "total_rows"],
        )

        details_schema = by_name[GET_JOB_DETAILS_TOOL].output_schema
        self.assertEqual(
            sorted(details_schema["properties"]), ["jobs", "not_fetched", "not_found"]
        )
        self.assertEqual(
            sorted(details_schema["required"]),
            ["jobs", "not_fetched", "not_found"],
        )

    async def test_query_clean_jobs_returns_the_typed_result(self) -> None:
        result = QueryResult(
            sql="SELECT count(*) AS count FROM clean_jobs",
            columns=["count"],
            rows=[[7]],
            row_count=1,
            total_rows=1,
        )
        behavior = AsyncMock(return_value=result)
        with patch("src.agents.mcp.job_server.run_query_clean_jobs", behavior):
            async with Client(create_job_mcp_server()) as client:
                call = await client.call_tool(
                    QUERY_CLEAN_JOBS_TOOL, {"request": "how many?"}
                )

        behavior.assert_awaited_once_with("how many?")
        self.assertFalse(call.is_error)
        self.assertEqual(call.structured_content, result.model_dump())

    async def test_get_job_details_returns_the_typed_result(self) -> None:
        result = JobDetailsResult(
            jobs=[{"id": 1, "title": "Intern A"}], not_found=[], not_fetched=[3]
        )
        behavior = AsyncMock(return_value=result)
        with patch("src.agents.mcp.job_server.run_get_job_details", behavior):
            async with Client(create_job_mcp_server()) as client:
                call = await client.call_tool(GET_JOB_DETAILS_TOOL, {"ids": [1, 3]})

        behavior.assert_awaited_once_with([1, 3])
        self.assertFalse(call.is_error)
        self.assertEqual(call.structured_content, result.model_dump())

    async def test_a_behavior_failure_carries_the_kind_and_the_detail(self) -> None:
        failure = ToolFailure("unknown_column", 'column "remote" does not exist')
        with patch(
            "src.agents.mcp.job_server.run_get_job_details",
            AsyncMock(side_effect=failure),
        ):
            async with Client(create_job_mcp_server()) as client:
                call = await client.call_tool(
                    GET_JOB_DETAILS_TOOL, {"ids": [1]}, raise_on_error=False
                )

        self.assertTrue(call.is_error)
        self.assertEqual(
            _text_of(call), 'unknown_column: column "remote" does not exist'
        )
        self.assertIsNone(call.structured_content)

    def test_a_recoverable_failure_is_logged_at_warning(self) -> None:
        # #744: a model-recoverable refusal is normal serving, so the MCP layer
        # must not log it as a server fault.
        error = to_tool_error(ToolFailure("rejected", "Only SELECT statements are allowed"))

        self.assertEqual(error.log_level, logging.WARNING)

    def test_an_unavailable_failure_is_logged_at_error(self) -> None:
        error = to_tool_error(
            ToolFailure("unavailable", "the database could not run the query")
        )

        self.assertEqual(error.log_level, logging.ERROR)

    async def test_a_behavior_failure_raises_by_default(self) -> None:
        failure = ToolFailure("unavailable", "the database could not run the query")
        with patch(
            "src.agents.mcp.job_server.run_query_clean_jobs",
            AsyncMock(side_effect=failure),
        ):
            async with Client(create_job_mcp_server()) as client:
                with self.assertRaises(ToolError) as raised:
                    await client.call_tool(QUERY_CLEAN_JOBS_TOOL, {"request": "x"})

        self.assertIn(
            "unavailable: the database could not run the query", str(raised.exception)
        )

    async def test_empty_ids_never_reach_the_behavior(self) -> None:
        behavior = AsyncMock(
            side_effect=AssertionError("the behavior must not run for empty ids")
        )
        with patch("src.agents.mcp.job_server.run_get_job_details", behavior):
            async with Client(create_job_mcp_server()) as client:
                call = await client.call_tool(
                    GET_JOB_DETAILS_TOOL, {"ids": []}, raise_on_error=False
                )

        behavior.assert_not_awaited()
        self.assertTrue(call.is_error)

    async def test_invalid_argument_types_never_reach_the_behavior(self) -> None:
        query_behavior = AsyncMock(side_effect=AssertionError("must not run"))
        details_behavior = AsyncMock(side_effect=AssertionError("must not run"))
        with (
            patch("src.agents.mcp.job_server.run_query_clean_jobs", query_behavior),
            patch("src.agents.mcp.job_server.run_get_job_details", details_behavior),
        ):
            async with Client(create_job_mcp_server()) as client:
                with self.assertRaises(ToolError):
                    await client.call_tool(GET_JOB_DETAILS_TOOL, {"ids": ["not-an-int"]})
                with self.assertRaises(ToolError):
                    await client.call_tool(QUERY_CLEAN_JOBS_TOOL, {"request": 42})

        query_behavior.assert_not_awaited()
        details_behavior.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
