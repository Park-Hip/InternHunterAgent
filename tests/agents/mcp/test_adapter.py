from __future__ import annotations

import unittest
from unittest.mock import patch

from src.agents.mcp.adapter import list_job_tools
from src.agents.mcp.job_server import create_job_mcp_server


class ListJobToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovers_the_two_job_query_tools_in_process(self) -> None:
        tools = await list_job_tools(create_job_mcp_server())

        self.assertEqual(
            sorted(tool.name for tool in tools),
            ["get_job_details", "query_clean_jobs"],
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


if __name__ == "__main__":
    unittest.main()