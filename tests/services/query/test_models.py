from __future__ import annotations

import unittest

from src.services.query.models import QueryRefusal, QueryToolResult, TableArtifact


class TableArtifactTests(unittest.TestCase):
    def test_table_artifact_serializes(self) -> None:
        table = TableArtifact(
            columns=["title", "company"],
            rows=[["Data Analyst", "Acme"]],
            row_count=1,
        )

        self.assertEqual(
            table.model_dump(),
            {
                "columns": ["title", "company"],
                "rows": [["Data Analyst", "Acme"]],
                "row_count": 1,
                "truncated": False,
            },
        )


class QueryRefusalTests(unittest.TestCase):
    def test_query_refusal_serializes(self) -> None:
        refusal = QueryRefusal(reason="unsafe SQL")

        self.assertEqual(
            refusal.model_dump(), {"reason": "unsafe SQL", "glossary_token": None}
        )


class QueryToolResultTests(unittest.TestCase):
    def test_query_tool_result_serializes(self) -> None:
        table = TableArtifact(columns=["title"], rows=[["ML Intern"]], row_count=1)
        result = QueryToolResult(answer="Found 1 job.", table=table, refusal=None)

        self.assertEqual(
            result.model_dump(),
            {
                "answer": "Found 1 job.",
                "table": {
                    "columns": ["title"],
                    "rows": [["ML Intern"]],
                    "row_count": 1,
                    "truncated": False,
                },
                "refusal": None,
                "obligations": [],
            },
        )
