"""The tool surface the agent's tool node really receives (#702).

Discovery is exercised against the in-process FastMCP server. The result tests
then invoke the discovered LangChain tools exactly as LangGraph does and assert
the message contract: typed JSON text plus the structured artifact on success,
and a ``status="error"`` tool message carrying ``"<kind>: <detail>"`` on a
behavior failure. That error message is the E4 regression: before #702 the
failure was a sentence, and the middleware reported it as a successful call.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import ToolMessage

from src.agents.mcp.adapter import list_job_tools
from src.agents.mcp.job_server import (
    GET_JOB_DETAILS_TOOL,
    QUERY_CLEAN_JOBS_TOOL,
    create_job_mcp_server,
)
from src.agents.tools.failures import ToolFailure
from src.services.query.models import JobDetailsResult, QueryResult


def _tool_call(name: str, args: dict, call_id: str = "call-1") -> dict:
    return {"type": "tool_call", "id": call_id, "name": name, "args": args}


def _text_of(message: ToolMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    return "".join(
        block.get("text", "") if isinstance(block, dict) else str(block)
        for block in message.content
    )


class ListJobToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovers_the_job_query_tools_in_process(self) -> None:
        tools = await list_job_tools(create_job_mcp_server())

        self.assertEqual(
            sorted(tool.name for tool in tools),
            [GET_JOB_DETAILS_TOOL, QUERY_CLEAN_JOBS_TOOL],
        )

    async def test_propagates_discovery_failure(self) -> None:
        class _FailingAdapter:
            async def __aenter__(self):
                raise RuntimeError("discovery failed")

            async def __aexit__(self, *_args):
                return None

        with patch(
            "src.agents.mcp.adapter.MCPAdapter", return_value=_FailingAdapter()
        ):
            with self.assertRaises(RuntimeError):
                await list_job_tools(object())


class AdapterToolResultTests(unittest.IsolatedAsyncioTestCase):
    """One real call per outcome, through the adapter the agent uses."""

    async def asyncSetUp(self) -> None:
        self.tools = {
            tool.name: tool for tool in await list_job_tools(create_job_mcp_server())
        }

    async def test_a_query_result_arrives_as_json_text_and_a_structured_artifact(
        self,
    ) -> None:
        result = QueryResult(
            sql="SELECT id, title FROM clean_jobs LIMIT 20",
            columns=["id", "title"],
            rows=[[1, "Kỹ sư AI"]],
            row_count=20,
            total_rows=161,
        )
        with patch(
            "src.agents.mcp.job_server.run_query_clean_jobs", return_value=result
        ):
            message = await self.tools[QUERY_CLEAN_JOBS_TOOL].ainvoke(
                _tool_call(QUERY_CLEAN_JOBS_TOOL, {"request": "việc làm AI"})
            )

        self.assertIsInstance(message, ToolMessage)
        self.assertEqual(message.status, "success")
        self.assertEqual(message.name, QUERY_CLEAN_JOBS_TOOL)
        text = _text_of(message)
        self.assertEqual(json.loads(text), result.model_dump())
        # Vietnamese must arrive as characters, not as \u escapes: an escaped
        # blob is unreadable to a reader and signals a JSON dump bug.
        self.assertIn("Kỹ sư AI", text)
        self.assertNotIn("\\u", text)
        self.assertEqual(
            message.artifact, {"structured_content": result.model_dump()}
        )

    async def test_a_details_result_arrives_as_json_text_and_a_structured_artifact(
        self,
    ) -> None:
        result = JobDetailsResult(jobs=[], not_found=[9], not_fetched=[7, 8])
        with patch(
            "src.agents.mcp.job_server.run_get_job_details", return_value=result
        ):
            message = await self.tools[GET_JOB_DETAILS_TOOL].ainvoke(
                _tool_call(GET_JOB_DETAILS_TOOL, {"ids": [9, 7, 8]})
            )

        self.assertEqual(message.status, "success")
        self.assertEqual(json.loads(_text_of(message)), result.model_dump())
        self.assertEqual(
            message.artifact, {"structured_content": result.model_dump()}
        )

    async def test_a_behavior_failure_is_an_error_message_not_an_exception(
        self,
    ) -> None:
        failure = ToolFailure("unknown_column", 'column "remote" does not exist')
        behavior = AsyncMock(side_effect=failure)
        with patch("src.agents.mcp.job_server.run_query_clean_jobs", behavior):
            message = await self.tools[QUERY_CLEAN_JOBS_TOOL].ainvoke(
                _tool_call(QUERY_CLEAN_JOBS_TOOL, {"request": "việc làm remote"})
            )

        self.assertIsInstance(message, ToolMessage)
        self.assertEqual(message.status, "error")
        self.assertEqual(
            _text_of(message), 'unknown_column: column "remote" does not exist'
        )
        self.assertIsNone(message.artifact)

    async def test_a_generation_failure_arrives_as_unavailable_without_raw_text(
        self,
    ) -> None:
        """#754: the SQL-generation call is inside the failure vocabulary."""
        raising = AsyncMock(
            side_effect=TimeoutError("provider timed out after 30 s at api.internal")
        )
        with patch("src.agents.tools.query_clean_jobs.generate_sql", raising):
            message = await self.tools[QUERY_CLEAN_JOBS_TOOL].ainvoke(
                _tool_call(QUERY_CLEAN_JOBS_TOOL, {"request": "việc làm AI"})
            )

        self.assertEqual(message.status, "error")
        self.assertEqual(
            _text_of(message), "unavailable: the SQL generator did not answer"
        )
        self.assertNotIn("timed out", _text_of(message))
        self.assertIsNone(message.artifact)

    async def test_empty_ids_are_refused_before_the_behavior_runs(self) -> None:
        behavior = AsyncMock(
            side_effect=AssertionError("the behavior must not run for empty ids")
        )
        with patch("src.agents.mcp.job_server.run_get_job_details", behavior):
            message = await self.tools[GET_JOB_DETAILS_TOOL].ainvoke(
                _tool_call(GET_JOB_DETAILS_TOOL, {"ids": []})
            )

        behavior.assert_not_awaited()
        self.assertEqual(message.status, "error")
        self.assertIn("at least 1 item", _text_of(message))


if __name__ == "__main__":
    unittest.main()
