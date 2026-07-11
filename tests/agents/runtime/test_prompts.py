from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from src.agents.runtime.prompts import (
    load_prompt_version,
    load_schema_context,
    load_sql_generation_prompt,
    load_system_prompt,
)


VISIBLE_16 = (
    "id",
    "title",
    "company",
    "role",
    "description",
    "tech_stack",
    "location",
    "source_url",
    "job_level",
    "listing_expires_on",
    "created_on",
    "is_internship",
    "salary_min",
    "salary_max",
    "salary_currency",
    "is_salary_negotiable",
)


def _schema_context_column_names(text: str) -> str:
    names: list[str] = []
    for line in text.splitlines():
        match = re.match(r"\s*-\s+([a-z_]+)\s+\(", line)
        if match:
            names.append(match.group(1))
    return ", ".join(names)


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


class LoadPromptVersionTests(unittest.TestCase):
    @patch("src.agents.runtime.prompts.settings")
    def test_load_prompt_version_returns_stripped_string(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"prompt_version": "  v2-few-shot  "}

        result = load_prompt_version()

        self.assertEqual(result, "v2-few-shot")

    @patch("src.agents.runtime.prompts.settings")
    def test_load_prompt_version_raises_when_key_missing(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {}

        with self.assertRaises(ValueError):
            load_prompt_version()

    @patch("src.agents.runtime.prompts.settings")
    def test_load_prompt_version_raises_when_blank(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"prompt_version": "   "}

        with self.assertRaises(ValueError):
            load_prompt_version()

    def test_yaml_prompt_version_is_non_empty(self) -> None:
        self.assertTrue(load_prompt_version())


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
        column_names = _schema_context_column_names(result)

        for column in VISIBLE_16:
            self.assertIn(column, result)

        for column in ("remote", "posted_date", "external_id"):
            self.assertNotIn(column, column_names)
        self.assertIsNone(
            re.search(r"\bsource\b", column_names),
            "hidden column 'source' leaked",
        )

    def test_yaml_schema_context_mentions_clean_jobs_table(self) -> None:
        result = load_schema_context()

        self.assertIn("clean_jobs", result)

    def test_system_prompt_available_fields_frozen(self) -> None:
        content = load_system_prompt().content
        line = next(
            line
            for line in content.splitlines()
            if "The database exposes these columns" in line
        )

        for column in VISIBLE_16:
            self.assertIn(column, line)
        for column in ("posted_date", "external_id"):
            self.assertNotIn(column, line)
        self.assertIsNone(
            re.search(r"\bsource\b", line),
            "hidden column 'source' leaked",
        )

    def test_sql_generation_real_columns_hide_hidden(self) -> None:
        line = next(
            line
            for line in load_sql_generation_prompt().splitlines()
            if "Reference only real columns" in line
        )

        for column in ("posted_date", "external_id"):
            self.assertNotIn(column, line)
        self.assertIsNone(
            re.search(r"\bsource\b", line),
            "hidden column 'source' leaked",
        )
