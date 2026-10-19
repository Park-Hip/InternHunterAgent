from __future__ import annotations

import re
import unittest
from typing import get_args
from unittest.mock import patch

from src.agents.runtime.prompts import (
    load_schema_context,
    load_sql_generation_prompt,
    load_system_prompt,
)
from src.agents.tools.failures import FailureKind
from src.services.query.models import JobDetailsResult, QueryResult


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


class SystemPromptContractTests(unittest.TestCase):
    """#708: wording is measured by evals/datasets/baseline.yaml, not pinned here.

    What stays pinned is the contract between the prompt and the tools: every
    result field, error kind, or column the prompt names in backticks must exist,
    so renaming a tool field cannot leave the prompt describing a field that is gone.
    """

    def test_every_name_in_backticks_exists_in_the_tool_contract(self) -> None:
        system_prompt = str(load_system_prompt().content)
        known = (
            set(QueryResult.model_fields)
            | set(JobDetailsResult.model_fields)
            | set(get_args(FailureKind))
            | set(re.findall(r"^- (\w+) \(", load_schema_context(), re.MULTILINE))
        )

        named = set(re.findall(r"`(\w+)`", system_prompt))

        self.assertTrue(named, "the system prompt names no tool result field")
        self.assertEqual(named - known, set())

    def test_system_prompt_no_longer_relays_tool_caveats(self) -> None:
        """#702: tools return facts, so there is no caveat text left to relay."""
        system_prompt = str(load_system_prompt().content)

        self.assertNotIn("MANDATORY CAVEATS", system_prompt)
        self.assertNotIn("reflect every caveat", system_prompt)
