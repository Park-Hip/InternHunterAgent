from __future__ import annotations

import unittest
from unittest.mock import patch

from src.agents.runtime.prompts import (
    load_behavior_glossary,
    load_prompt_version,
    load_schema_context,
    load_sql_generation_prompt,
    load_system_prompt,
)

# The frozen G47 token set (18 entries, frozen 2026-07-11 by T0015.2). Recovered from
# archive/t0015.2-behavior-glossary. Adding or removing a token is a behavior-spec change,
# not a code change - update docs/Agent_Behavior_Spec.md first.
FROZEN_GLOSSARY_TOKENS = frozenset({
    "NEGOTIABLE_SALARY", "ABSENT_FIELD", "FRESHNESS_REFUSAL", "CREATED_ON_CAVEAT",
    "FREE_TEXT_HEDGE", "SENIOR_TITLE_HEDGE", "CROSS_CURRENCY", "TRUNCATION",
    "ZERO_RESULTS", "E1_CLARIFY", "OFF_TOPIC_REDIRECT", "DESTRUCTIVE_REFUSAL",
    "INJECTION_REFUSAL", "SECRET_REFUSAL", "SQL_DESCRIBE_ONLY", "FUTURE_FEATURE",
    "GENERAL_KNOWLEDGE_DECLINE", "DISCRIMINATORY_DECLINE",
})


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


class SystemPromptScopeTests(unittest.TestCase):
    """Settled behavior decision #10: the persona describes the corpus it actually has."""

    NARROWING_PHRASES = (
        "internship and job postings",
        "outside internship/job postings",
        "internship/job postings",
    )

    def test_persona_and_decline_lines_state_the_corrected_scope(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn(
            "helps users explore AI/Data job and internship postings", system_prompt
        )
        self.assertIn(
            "decline anything outside AI/Data job and internship postings", system_prompt
        )

    def test_system_prompt_carries_no_internship_first_narrowing(self) -> None:
        system_prompt = str(load_system_prompt().content)

        for phrase in self.NARROWING_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, system_prompt)


class LoadPromptVersionTests(unittest.TestCase):
    @patch("src.agents.runtime.prompts.settings")
    def test_returns_stripped_string(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"prompt_version": "  v2  "}

        self.assertEqual(load_prompt_version(), "v2")

    @patch("src.agents.runtime.prompts.settings")
    def test_raises_when_missing(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"prompts": {}}

        with self.assertRaises(ValueError):
            load_prompt_version()

    @patch("src.agents.runtime.prompts.settings")
    def test_raises_when_blank(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"prompt_version": "   "}

        with self.assertRaises(ValueError):
            load_prompt_version()

    def test_yaml_declares_a_prompt_version(self) -> None:
        self.assertEqual(load_prompt_version(), "v2")


class LoadBehaviorGlossaryTests(unittest.TestCase):
    @patch("src.agents.runtime.prompts.settings")
    def test_returns_stripped_mapping(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"behavior_glossary": {"ZERO_RESULTS": "  nothing found  "}}

        self.assertEqual(load_behavior_glossary(), {"ZERO_RESULTS": "nothing found"})

    @patch("src.agents.runtime.prompts.settings")
    def test_raises_when_missing(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"prompts": {}}

        with self.assertRaises(ValueError):
            load_behavior_glossary()

    @patch("src.agents.runtime.prompts.settings")
    def test_raises_when_empty(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"behavior_glossary": {}}

        with self.assertRaises(ValueError):
            load_behavior_glossary()

    @patch("src.agents.runtime.prompts.settings")
    def test_raises_when_a_phrasing_is_blank(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {
            "behavior_glossary": {"ZERO_RESULTS": "nothing found", "TRUNCATION": "   "}
        }

        with self.assertRaises(ValueError):
            load_behavior_glossary()

    def test_yaml_glossary_covers_every_frozen_token(self) -> None:
        self.assertEqual(set(load_behavior_glossary()), set(FROZEN_GLOSSARY_TOKENS))

    def test_yaml_glossary_phrasings_are_non_empty(self) -> None:
        for token, phrasing in load_behavior_glossary().items():
            with self.subTest(token=token):
                self.assertTrue(phrasing.strip())

    def test_glossary_is_not_pasted_into_the_system_prompt(self) -> None:
        system_prompt = str(load_system_prompt().content)

        for token, phrasing in load_behavior_glossary().items():
            with self.subTest(token=token):
                self.assertNotIn(phrasing, system_prompt)
