from __future__ import annotations

import unittest

from src.services.query.models import HedgeObligation, QueryToolResult, TableArtifact
from src.services.query.obligations import detect_obligations, detect_row_obligations
from src.services.query.table_formatter import render_tool_result


class DetectObligationsTests(unittest.TestCase):
    def test_listing_expiry_query_requires_not_deadline_caveat(self) -> None:
        table = TableArtifact(
            columns=["title", "listing_expires_on"],
            rows=[["Data Analyst", "2026-09-01"]],
            row_count=1,
        )

        obligations = detect_obligations(
            "SELECT title, listing_expires_on FROM clean_jobs", table
        )

        self.assertEqual(
            [obligation.glossary_token for obligation in obligations],
            ["LISTING_EXPIRY_NOT_DEADLINE"],
        )

    def test_created_on_and_free_text_queries_require_both_caveats(self) -> None:
        table = TableArtifact(columns=["title"], rows=[["Data Analyst"]], row_count=1)

        obligations = detect_obligations(
            "SELECT title FROM clean_jobs WHERE description ILIKE '%remote%' ORDER BY created_on DESC",
            table,
        )

        self.assertEqual(
            [obligation.glossary_token for obligation in obligations],
            ["CREATED_ON_CAVEAT", "FREE_TEXT_HEDGE"],
        )

    def test_missing_salary_values_require_negotiable_salary_caveat(self) -> None:
        table = TableArtifact(
            columns=["salary_min", "salary_max"],
            rows=[[None, None]],
            row_count=1,
        )

        obligations = detect_obligations("SELECT salary_min, salary_max FROM clean_jobs", table)

        self.assertEqual(
            [obligation.glossary_token for obligation in obligations],
            ["NEGOTIABLE_SALARY"],
        )

    def test_renderer_marks_listing_expiry_caveat_for_the_agent(self) -> None:
        glossary = {"LISTING_EXPIRY_NOT_DEADLINE": "listing expiry is not a deadline"}
        result = QueryToolResult(
            table=TableArtifact(columns=["title"], rows=[["Data Analyst"]], row_count=1),
            obligations=[HedgeObligation(glossary_token="LISTING_EXPIRY_NOT_DEADLINE")],
        )

        rendered = render_tool_result(result, glossary)

        self.assertIn("MANDATORY CAVEATS:", rendered)
        self.assertIn("[LISTING_EXPIRY_NOT_DEADLINE] listing expiry is not a deadline", rendered)

    def test_row_only_detection_does_not_apply_query_shape_rules(self) -> None:
        table = TableArtifact(
            columns=["listing_expires_on", "is_salary_negotiable"],
            rows=[["2026-09-01", True]],
            row_count=1,
        )

        obligations = detect_row_obligations(table)

        self.assertEqual(
            [obligation.glossary_token for obligation in obligations],
            ["NEGOTIABLE_SALARY"],
        )
