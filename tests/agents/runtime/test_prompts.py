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

# The G47 token set includes the listing-expiry schema fact added by T0024.2. Recovered from
# archive/t0015.2-behavior-glossary. Adding or removing a token is a behavior-spec change,
# not a code change - update docs/Agent_Behavior_Spec.md first.
FROZEN_GLOSSARY_TOKENS = frozenset({
    "NEGOTIABLE_SALARY", "ABSENT_FIELD", "FRESHNESS_REFUSAL", "CREATED_ON_CAVEAT",
    "LISTING_EXPIRY_NOT_DEADLINE",
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

    def test_persona_line_states_the_corrected_scope(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn(
            "helps users explore AI/Data job and internship postings", system_prompt
        )

    def test_system_prompt_names_internships_only_in_its_identity_line(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertEqual(system_prompt.lower().count("internship"), 1)

    def test_system_prompt_states_date_semantics_and_absent_deadlines(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn("listing-expiry date is not an application deadline", system_prompt)
        self.assertIn("creation date is not a publication date", system_prompt)
        self.assertIn("does not contain application deadlines", system_prompt)

    def test_system_prompt_clarifies_ambiguous_initial_requests(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn("If a request is genuinely ambiguous", system_prompt)
        self.assertIn("ask exactly one clarifying question", system_prompt)

    def test_system_prompt_requires_mandatory_caveats_to_survive_the_relay(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn("MANDATORY CAVEATS", system_prompt)
        self.assertIn("reflect every caveat", system_prompt)
        self.assertIn("must not weaken or omit", system_prompt)
        self.assertIn("the caveat wins", system_prompt)

    def test_system_prompt_forbids_emoji_and_decorative_symbols(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn("Do not use emoji or decorative symbols", system_prompt)


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
        self.assertEqual(load_prompt_version(), "v8")


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
