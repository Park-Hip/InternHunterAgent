from __future__ import annotations

import unittest
from unittest.mock import patch

from src.agents.runtime.prompts import (
    load_prompt_versions,
    load_schema_context,
    load_sql_generation_prompt,
    load_system_prompt,
)


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

    def test_system_prompt_no_longer_relays_tool_caveats(self) -> None:
        """#702: tools return facts, so there is no caveat text left to relay."""
        system_prompt = str(load_system_prompt().content)

        self.assertNotIn("MANDATORY CAVEATS", system_prompt)
        self.assertNotIn("reflect every caveat", system_prompt)

    def test_system_prompt_forbids_emoji_and_decorative_symbols(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn("Do not use emoji or decorative symbols", system_prompt)

    def test_system_prompt_requires_safe_original_source_links(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn("labelled original source link", system_prompt)
        self.assertIn("do not claim that the posting is open, available, or closed", system_prompt)


class LoadPromptVersionsTests(unittest.TestCase):
    @patch("src.agents.runtime.prompts.settings")
    def test_returns_stripped_named_versions(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {
            "prompt_versions": {
                "system": "  v2  ",
                "schema_context": "v3",
                "sql_generation": "v4",
            }
        }

        self.assertEqual(
            load_prompt_versions(),
            {"system": "v2", "schema_context": "v3", "sql_generation": "v4"},
        )

    @patch("src.agents.runtime.prompts.settings")
    def test_raises_when_missing(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {"prompts": {}}

        with self.assertRaises(ValueError):
            load_prompt_versions()

    @patch("src.agents.runtime.prompts.settings")
    def test_raises_when_blank(self, mock_settings) -> None:
        mock_settings.prompts_yaml = {
            "prompt_versions": {
                "system": "v2",
                "schema_context": "v3",
                "sql_generation": "   ",
            }
        }

        with self.assertRaises(ValueError):
            load_prompt_versions()

    def test_yaml_declares_independent_prompt_versions(self) -> None:
        assert load_prompt_versions() == {
            "system": "v14",
            "schema_context": "v12",
            "sql_generation": "v15",
        }

    def test_yaml_sql_rules_carry_the_issue_243_superlative_and_salary_contract(self) -> None:
        sql_generation = load_sql_generation_prompt()

        # Issue #243 capture 2026-08-26: superlative questions returned whole tables that
        # were then silently truncated in the answer, dropping labelled source links.
        self.assertIn("add LIMIT 1 so only that top row is returned", sql_generation)
        # Repeat 3 of HON-NEGOTIABLE-SALARY-1 filtered on salary disclosure and
        # substituted a zero-results report for the negotiable-salary answer.
        self.assertIn("never add a salary-disclosure filter", sql_generation)

    def test_yaml_sql_rules_carry_the_issue_251_abstraction_contract(self) -> None:
        sql_generation = load_sql_generation_prompt()

        # Issue #251 capture 2026-08-26: all 3 v10 repeats of HLP-ABSTRACTION-1
        # ("Việc làm ML?") added role ILIKE '%ML Engineer%'/'%Machine Learning%'
        # clauses alongside the tech_stack/title/description match, pulling in rows
        # that never mention "machine learning" anywhere in their own text.
        self.assertIn("Do NOT add role-category filters", sql_generation)
        self.assertIn("role ILIKE '%ML Engineer%'", sql_generation)
        # Second v11 capture iteration: the bare abbreviation '%ML%' also matched
        # "MLOps" and "MLflow", so the rule must require the expanded form only.
        self.assertIn("do NOT also search the bare abbreviation", sql_generation)

    def test_yaml_sql_rules_require_grouping_salary_aggregates_by_currency(self) -> None:
        sql_generation = load_sql_generation_prompt()

        # #702: the cross-currency rule moved out of the deleted obligation layer
        # and into the only prompt that can act on it, before the aggregate runs.
        self.assertIn(
            "Every salary aggregate (AVG, MIN, MAX, SUM) groups by salary_currency",
            sql_generation,
        )
        self.assertIn("Never aggregate salaries across currencies", sql_generation)


class ToolResultReadingTests(unittest.TestCase):
    """v14 (#702): the tools return typed facts, so the prompt owns every word.

    The behaviors no longer write sentences: `query_clean_jobs` returns `sql`,
    `columns`, `rows`, `row_count`, and `total_rows`, and failures arrive as
    error-status messages. These assertions pin the prompt rules that replaced
    the free-text caveat machinery, so wording cannot silently vanish.
    """

    def test_the_reading_tool_results_section_appears_exactly_once(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertEqual(system_prompt.count("# Reading tool results"), 1)

    def test_the_sql_that_ran_is_internal_and_never_shown(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn("The `sql` in a query result is internal", system_prompt)
        self.assertIn("Never show it, quote it, or name its columns", system_prompt)

    def test_zero_results_and_truncation_have_plain_language(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn("If `total_rows` is 0, or a count in `rows` is 0", system_prompt)
        self.assertIn("say plainly that no posting matched", system_prompt)
        self.assertIn("say you are showing `row_count` of `total_rows` postings", system_prompt)

    def test_a_summary_reports_the_figures_in_rows_not_the_row_count(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn(
            "A count or summary carries its figures in `rows`. Report those figures, not `row_count`",
            system_prompt,
        )

    def test_a_description_match_is_named_and_a_structured_match_is_not_hedged(
        self,
    ) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn(
            "A term matched only through `description ILIKE` was found in the posting text",
            system_prompt,
        )
        self.assertIn("Never say the data lacks a field that the query used", system_prompt)

    def test_job_details_not_found_and_not_fetched_are_stated_plainly(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn(
            "say plainly when a requested posting was not found", system_prompt
        )
        self.assertIn("Call again for `not_fetched` ids", system_prompt)

    def test_a_tool_error_is_explained_without_technical_detail(self) -> None:
        system_prompt = str(load_system_prompt().content)

        self.assertIn("On a tool error, explain in Vietnamese without technical detail", system_prompt)
        self.assertIn("For `unknown_column`, say the data does not record that information", system_prompt)
