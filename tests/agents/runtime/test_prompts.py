from __future__ import annotations

import unittest
from unittest.mock import patch

from src.agents.runtime.prompts import load_schema_context, load_sql_generation_prompt


class LoadSqlGenerationPromptTests(unittest.TestCase):
    @patch("src.agents.runtime.prompts.settings")
    def test_load_sql_generation_prompt_returns_stripped_string(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {
            "prompts": {"sql_generation": "  SELECT-only. Always include LIMIT.  "}
        }

        result = load_sql_generation_prompt()

        self.assertEqual(result, "SELECT-only. Always include LIMIT.")

    @patch("src.agents.runtime.prompts.settings")
    def test_load_sql_generation_prompt_raises_when_prompts_section_missing(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {}

        with self.assertRaises(ValueError):
            load_sql_generation_prompt()

    @patch("src.agents.runtime.prompts.settings")
    def test_load_sql_generation_prompt_raises_when_sql_generation_missing(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"prompts": {}}

        with self.assertRaises(ValueError):
            load_sql_generation_prompt()

    @patch("src.agents.runtime.prompts.settings")
    def test_load_sql_generation_prompt_raises_when_sql_generation_blank(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"prompts": {"sql_generation": "   "}}

        with self.assertRaises(ValueError):
            load_sql_generation_prompt()


class LoadSchemaContextTests(unittest.TestCase):
    @patch("src.agents.runtime.prompts.settings")
    def test_returns_stripped_string(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {
            "prompts": {"schema_context": "  Table: clean_jobs\nColumns: title  "}
        }

        result = load_schema_context()

        self.assertEqual(result, "Table: clean_jobs\nColumns: title")

    @patch("src.agents.runtime.prompts.settings")
    def test_raises_when_prompts_section_missing(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {}

        with self.assertRaises(ValueError):
            load_schema_context()

    @patch("src.agents.runtime.prompts.settings")
    def test_raises_when_schema_context_missing(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"prompts": {}}

        with self.assertRaises(ValueError):
            load_schema_context()

    @patch("src.agents.runtime.prompts.settings")
    def test_raises_when_schema_context_blank(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"prompts": {"schema_context": "   "}}

        with self.assertRaises(ValueError):
            load_schema_context()

    def test_yaml_schema_context_mentions_rich_schema(self) -> None:
        result = load_schema_context()

        for column in (
            "id", "title", "company", "role", "description", "tech_stack",
            "location", "source_url", "is_internship",
            "salary_min", "salary_max", "salary_currency", "is_salary_negotiable",
        ):
            self.assertIn(column, result)

        for column in ("remote", "posted_date", "is_active", "first_seen_at", "last_seen_at"):
            self.assertNotIn(column, result)

    def test_yaml_schema_context_mentions_clean_jobs_table(self) -> None:
        result = load_schema_context()

        self.assertIn("clean_jobs", result)
