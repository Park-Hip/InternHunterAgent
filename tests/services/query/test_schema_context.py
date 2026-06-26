from __future__ import annotations

import unittest

from src.services.query.schema_context import build_clean_jobs_schema_context


class BuildCleanJobsSchemaContextTests(unittest.TestCase):
    def test_mentions_only_the_four_advertised_columns(self) -> None:
        context = build_clean_jobs_schema_context()

        for column in ("title", "company", "description", "tech_stack"):
            self.assertIn(column, context)

        for column in ("salary_min", "salary_max", "location", "remote", "id"):
            self.assertNotIn(column, context)

    def test_mentions_the_clean_jobs_table(self) -> None:
        context = build_clean_jobs_schema_context()

        self.assertIn("clean_jobs", context)
