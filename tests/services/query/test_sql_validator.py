import re
import unittest
from pathlib import Path

import yaml

from src.services.query.sql_validator import (
    HIDDEN_COLUMNS,
    has_id_tiebreak,
    validate_sql,
)

PROMPTS_PATH = Path(__file__).resolve().parents[3] / "config" / "prompts.yaml"
# The one line in `sql_generation` that declares the agent-visible columns. The
# audit script (`scripts/audit_sql_prompt_columns.py`) gates the same wording.
DECLARED_PATTERN = re.compile(
    r"Reference only real columns:\s*(.+?)\.\s+Never invent a column", re.DOTALL
)


class ValidateSqlTests(unittest.TestCase):
    def test_allows_simple_select_on_clean_jobs(self) -> None:
        result = validate_sql("SELECT title FROM clean_jobs LIMIT 10")

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")

    def test_rejects_delete(self) -> None:
        result = validate_sql("DELETE FROM clean_jobs")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_insert(self) -> None:
        result = validate_sql("INSERT INTO clean_jobs (title) VALUES ('Intern')")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_update(self) -> None:
        result = validate_sql("UPDATE clean_jobs SET title = 'x'")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_drop(self) -> None:
        result = validate_sql("DROP TABLE clean_jobs")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_ddl_alter(self) -> None:
        result = validate_sql("ALTER TABLE clean_jobs ADD COLUMN salary int")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_multi_statement(self) -> None:
        result = validate_sql("SELECT * FROM clean_jobs; DELETE FROM clean_jobs")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_unknown_table(self) -> None:
        result = validate_sql("SELECT * FROM other_table")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_system_table(self) -> None:
        result = validate_sql("SELECT * FROM pg_tables")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_information_schema(self) -> None:
        result = validate_sql("SELECT * FROM information_schema.tables")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_comment_injection(self) -> None:
        result = validate_sql("SELECT title FROM clean_jobs -- comment")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_block_comment_injection(self) -> None:
        result = validate_sql("SELECT title FROM clean_jobs /* comment */")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_tolerates_leading_and_surrounding_whitespace(self) -> None:
        result = validate_sql("   SELECT title FROM clean_jobs LIMIT 10   ")

        self.assertTrue(result.valid)
        self.assertEqual(result.sql, "SELECT title FROM clean_jobs LIMIT 10")

    def test_rejects_join_to_other_table(self) -> None:
        result = validate_sql(
            "SELECT * FROM clean_jobs JOIN raw_jobs USING (source, external_id)"
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_comma_join_to_other_table(self) -> None:
        result = validate_sql("SELECT c.title FROM clean_jobs c, raw_jobs r")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_comma_join_with_as_aliases(self) -> None:
        result = validate_sql("SELECT * FROM clean_jobs AS c, raw_jobs AS r")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_comma_join_with_delimited_alias(self) -> None:
        result = validate_sql('SELECT * FROM clean_jobs AS "c", raw_jobs')

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_comma_join_with_alias_column_list(self) -> None:
        result = validate_sql("SELECT * FROM clean_jobs AS c(title), raw_jobs")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_comma_join_after_only_inheritance_marker(self) -> None:
        result = validate_sql("SELECT * FROM ONLY clean_jobs *, raw_jobs")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_comma_join_with_delimited_alias_column(self) -> None:
        result = validate_sql('SELECT * FROM clean_jobs AS c(")"), raw_jobs')

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_comma_join_with_unicode_delimited_alias(self) -> None:
        result = validate_sql('SELECT * FROM clean_jobs AS U&"c\\0061", raw_jobs')

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_bare_select_from_other_table(self) -> None:
        result = validate_sql("SELECT * FROM raw_jobs")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_allows_clean_jobs_query_with_where_clause(self) -> None:
        result = validate_sql(
            "SELECT title, company FROM clean_jobs WHERE location = 'Hanoi'"
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")

    def test_allows_clean_jobs_query_with_other_table_name_in_string_literal(
        self,
    ) -> None:
        result = validate_sql(
            "SELECT title FROM clean_jobs WHERE description ILIKE '%raw_jobs%'"
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")

    def test_allows_table_less_select(self) -> None:
        result = validate_sql("SELECT 1")

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")

    def test_allows_denylisted_word_inside_string_literal(self) -> None:
        result = validate_sql(
            "SELECT * FROM clean_jobs WHERE description ILIKE '%replace%'"
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")

    def test_allows_denylisted_word_as_literal_value(self) -> None:
        result = validate_sql("SELECT * FROM clean_jobs WHERE company_name = 'Merge'")

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")

    def test_rejects_denylisted_verb_outside_literal(self) -> None:
        result = validate_sql(
            "SELECT * FROM clean_jobs UPDATE SET title = 'x'"
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_select_into(self) -> None:
        result = validate_sql("SELECT * INTO raw_jobs FROM clean_jobs")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_large_object_import(self) -> None:
        result = validate_sql("SELECT *, lo_import('/etc/passwd') FROM clean_jobs")

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_function_name_with_dangerous_suffix(self) -> None:
        # `x$lo_import` is its own function name, not `lo_import`; the allowlist
        # reads the parsed name and refuses it as an unknown function (#742).
        result = validate_sql("SELECT x$lo_import('/tmp/x') FROM clean_jobs")

        self.assertFalse(result.valid)
        self.assertIn("Function is not allowed", result.reason)

    def test_rejects_dblink_function(self) -> None:
        result = validate_sql(
            "SELECT dblink_connect('host=internal.example') FROM clean_jobs"
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_quoted_large_object_import(self) -> None:
        result = validate_sql('SELECT "lo_import"(\'/etc/passwd\') FROM clean_jobs')

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_case_distinct_quoted_function(self) -> None:
        # A quoted identifier keeps its case, so this calls `LO_IMPORT`, which
        # is not the allowlisted `lo_import` (PostgreSQL would not find it
        # either).
        result = validate_sql('SELECT "LO_IMPORT"(1) FROM clean_jobs')

        self.assertFalse(result.valid)
        self.assertIn("Function is not allowed", result.reason)

    def test_rejects_schema_qualified_quoted_dblink_function(self) -> None:
        result = validate_sql(
            'SELECT "public"."dblink_connect"(\'host=internal.example\') FROM clean_jobs'
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_allows_dangerous_function_text_in_dollar_quoted_literal(self) -> None:
        result = validate_sql(
            "SELECT $payload$lo_import('/etc/passwd')$payload$ FROM clean_jobs"
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")

    def test_rejects_dangerous_function_after_escape_string_literal(self) -> None:
        result = validate_sql(
            "SELECT E'foo\\\'' || lo_import('/etc/passwd') FROM clean_jobs"
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_unicode_escaped_large_object_import(self) -> None:
        result = validate_sql(
            "SELECT U&\"lo\\005fimport\"('/etc/passwd') FROM clean_jobs"
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_custom_unicode_escaped_blocking_function(self) -> None:
        result = validate_sql(
            "SELECT U&\"pg!005fsleep\" UESCAPE '!'(10) FROM clean_jobs"
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_invalid_unicode_code_point(self) -> None:
        result = validate_sql(
            "SELECT U&\"lo\\+FFFFFF\"('/etc/passwd') FROM clean_jobs"
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_unicode_escaped_non_allowlisted_table(self) -> None:
        result = validate_sql('SELECT * FROM U&"raw\\005fjobs"')

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_unicode_escaped_table_with_embedded_quote(self) -> None:
        result = validate_sql('SELECT * FROM U&"clean_jobs\\0022raw"')

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_dangerous_function_before_dollar_quoted_literal(self) -> None:
        result = validate_sql(
            "SELECT 1 AS x$tag$, lo_import('/etc/passwd'), $tag$foo$tag$ FROM clean_jobs"
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_dangerous_function_after_quoted_dollar_tag(self) -> None:
        result = validate_sql(
            'SELECT "$tag$", lo_import(\'/etc/passwd\'), $tag$foo$tag$ FROM clean_jobs'
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_dangerous_function_after_non_ascii_identifier(self) -> None:
        result = validate_sql(
            "SELECT 1 AS 😀$tag$, lo_import('/etc/passwd'), $tag$foo$tag$ FROM clean_jobs"
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_escape_string_unicode_escaped_large_object_import(self) -> None:
        result = validate_sql(
            "SELECT U&\"lo!005fimport\" UESCAPE E'!'('/etc/passwd') FROM clean_jobs"
        )

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_unicode_escaped_system_table(self) -> None:
        result = validate_sql('SELECT * FROM U&"pg\\005fclass"')

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_rejects_unicode_escaped_table_after_only(self) -> None:
        result = validate_sql('SELECT * FROM ONLY U&"raw\\005fjobs"')

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_allows_clean_jobs_after_only(self) -> None:
        result = validate_sql("SELECT * FROM ONLY clean_jobs")

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")

    def test_rejects_case_distinct_delimited_table(self) -> None:
        result = validate_sql('SELECT * FROM "CLEAN_JOBS"')

        self.assertFalse(result.valid)
        self.assertTrue(result.reason)

    def test_allows_denylisted_keyword_as_delimited_identifier(self) -> None:
        result = validate_sql('SELECT title AS "into", company AS "copy" FROM clean_jobs')

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")

    def test_allows_dangerous_function_text_in_non_ascii_dollar_quote(self) -> None:
        result = validate_sql("SELECT $é$lo_import('/etc/passwd')$é$ FROM clean_jobs")

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")

    def test_allows_dangerous_function_text_in_emoji_dollar_quote(self) -> None:
        result = validate_sql("SELECT $😀$lo_import('/etc/passwd')$😀$ FROM clean_jobs")

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")


class ParsedStatementShapeTests(unittest.TestCase):
    """#742: the statement shape is read from PostgreSQL's parse tree.

    These are the probe cases from #617 row 5 and #736: a CTE, a parenthesised
    SELECT, a set-returning function in FROM, server identity functions, and
    the bound forms (FETCH FIRST, LIMIT ALL, a non-literal LIMIT) that the text
    scans refused with the wrong reason or corrupted.
    """

    def test_accepts_a_cte(self) -> None:
        result = validate_sql(
            "WITH per_city AS ("
            "SELECT trim(one_city) AS city, count(*) AS count "
            "FROM clean_jobs, string_to_table(location, ',') AS one_city "
            "GROUP BY 1) "
            "SELECT city, count FROM per_city ORDER BY count DESC, city"
        )

        self.assertTrue(result.valid, result.reason)

    def test_accepts_a_parenthesised_select(self) -> None:
        result = validate_sql("(SELECT id, title FROM clean_jobs ORDER BY id)")

        self.assertTrue(result.valid, result.reason)

    def test_accepts_a_parenthesised_select_with_its_own_limit(self) -> None:
        result = validate_sql("(SELECT id FROM clean_jobs ORDER BY id LIMIT 3)")

        self.assertTrue(result.valid, result.reason)

    def test_accepts_like_with_an_escape_character(self) -> None:
        # PostgreSQL rewrites LIKE ... ESCAPE into the like_escape helper, so
        # the tree names a function the model did not write.
        result = validate_sql(
            "SELECT id FROM clean_jobs WHERE title LIKE '%100\\%' ESCAPE '\\'"
        )

        self.assertTrue(result.valid, result.reason)

    def test_accepts_similar_to(self) -> None:
        result = validate_sql(
            "SELECT id FROM clean_jobs WHERE title SIMILAR TO '%(Python|SQL)%'"
        )

        self.assertTrue(result.valid, result.reason)

    def test_accepts_string_to_table_in_a_lateral_join(self) -> None:
        result = validate_sql(
            "SELECT one_city, count(*) AS count FROM clean_jobs "
            "CROSS JOIN LATERAL string_to_table(location, ',') AS one_city "
            "GROUP BY one_city ORDER BY count DESC, one_city"
        )

        self.assertTrue(result.valid, result.reason)

    def test_accepts_unnest_of_string_to_array(self) -> None:
        result = validate_sql(
            "SELECT one_tech, count(*) AS count FROM clean_jobs, "
            "unnest(string_to_array(tech_stack, ',')) AS one_tech "
            "GROUP BY one_tech ORDER BY count DESC, one_tech"
        )

        self.assertTrue(result.valid, result.reason)

    def test_accepts_a_set_operation(self) -> None:
        result = validate_sql(
            "SELECT id FROM clean_jobs WHERE is_internship "
            "UNION SELECT id FROM clean_jobs WHERE job_level = 'Fresher/Entry level' "
            "ORDER BY id"
        )

        self.assertTrue(result.valid, result.reason)

    def test_accepts_one_reference_per_scope(self) -> None:
        # The guard dataset's A02: the outer query and a scalar subquery each
        # read clean_jobs once. That is two scopes, not a self-join.
        result = validate_sql(
            "SELECT id FROM clean_jobs "
            "WHERE salary_max >= (SELECT avg(salary_max) FROM clean_jobs)"
        )

        self.assertTrue(result.valid, result.reason)

    def test_accepts_public_clean_jobs(self) -> None:
        result = validate_sql("SELECT id FROM public.clean_jobs ORDER BY id")

        self.assertTrue(result.valid, result.reason)

    def test_accepts_comment_text_inside_a_string_literal(self) -> None:
        result = validate_sql(
            "SELECT id FROM clean_jobs WHERE title <> 'a -- b /* c */'"
        )

        self.assertTrue(result.valid, result.reason)

    def test_treats_a_cte_name_as_local(self) -> None:
        result = validate_sql(
            "WITH raw_jobs AS (SELECT id FROM clean_jobs) "
            "SELECT id FROM raw_jobs ORDER BY id"
        )

        self.assertTrue(result.valid, result.reason)

    def test_reads_a_non_recursive_cte_self_reference_as_a_table(self) -> None:
        # Without RECURSIVE the name inside the CTE body is the real table, so
        # the tree, not the name alone, decides what was read.
        result = validate_sql(
            "WITH raw_jobs AS (SELECT id FROM raw_jobs) SELECT id FROM raw_jobs"
        )

        self.assertFalse(result.valid)
        self.assertIn("may only reference the clean_jobs table: raw_jobs", result.reason)

    def test_a_recursive_cte_may_reference_itself(self) -> None:
        result = validate_sql(
            "WITH RECURSIVE numbers AS ("
            "SELECT 1 AS n UNION ALL SELECT n + 1 FROM numbers WHERE n < 5) "
            "SELECT n FROM numbers"
        )

        self.assertTrue(result.valid, result.reason)

    def test_accepts_an_allowlisted_schema_qualified_function(self) -> None:
        result = validate_sql("SELECT pg_catalog.lower(title) FROM clean_jobs")

        self.assertTrue(result.valid, result.reason)

    def test_accepts_a_visible_column_aliased_with_a_hidden_name(self) -> None:
        # The alias is output naming, not a read of the hidden column.
        result = validate_sql("SELECT title AS source FROM clean_jobs")

        self.assertTrue(result.valid, result.reason)

    def test_rejects_each_server_identity_function(self) -> None:
        cases = {
            "SELECT version()": "version",
            "SELECT current_user": "current_user",
            "SELECT current_database()": "current_database",
            "SELECT inet_server_addr()": "inet_server_addr",
            "SELECT current_setting('data_directory')": "current_setting",
            "SELECT pg_backend_pid()": "pg_backend_pid",
            "SELECT current_catalog": "current_catalog",
        }
        for sql, name in cases.items():
            with self.subTest(sql=sql):
                result = validate_sql(sql)

                self.assertFalse(result.valid)
                self.assertIn(
                    "Server identity functions are not allowed", result.reason
                )
                self.assertIn(name, result.reason)

    def test_rejects_a_schema_qualified_identity_function(self) -> None:
        result = validate_sql("SELECT pg_catalog.version()")

        self.assertFalse(result.valid)
        self.assertIn("Server identity functions are not allowed: version", result.reason)

    def test_rejects_a_function_outside_the_allowlist(self) -> None:
        result = validate_sql("SELECT md5(title) FROM clean_jobs")

        self.assertFalse(result.valid)
        self.assertIn("Function is not allowed: md5", result.reason)

    def test_rejects_a_data_modifying_cte(self) -> None:
        result = validate_sql(
            "WITH removed AS (DELETE FROM clean_jobs RETURNING id) "
            "SELECT count(*) AS count FROM removed"
        )

        self.assertFalse(result.valid)
        self.assertIn("Data-modifying statements are not allowed", result.reason)

    def test_rejects_a_row_locking_clause(self) -> None:
        result = validate_sql("SELECT id FROM clean_jobs FOR UPDATE")

        self.assertFalse(result.valid)
        self.assertIn("Row locking clauses are not allowed", result.reason)

    def test_rejects_a_self_join(self) -> None:
        result = validate_sql(
            "SELECT count(*) AS count FROM clean_jobs a JOIN clean_jobs b "
            "ON a.location = b.location"
        )

        self.assertFalse(result.valid)
        self.assertIn("may only reference the clean_jobs table once", result.reason)

    def test_rejects_pg_catalog_schema(self) -> None:
        result = validate_sql("SELECT relname FROM pg_catalog.pg_class")

        self.assertFalse(result.valid)
        self.assertIn("Access to system tables is not allowed", result.reason)

    def test_rejects_a_hidden_column_in_a_subquery(self) -> None:
        result = validate_sql(
            "SELECT id FROM (SELECT external_id AS id FROM clean_jobs) AS q"
        )

        self.assertFalse(result.valid)
        self.assertIn("Hidden column", result.reason)

    def test_rejects_a_non_literal_limit(self) -> None:
        result = validate_sql("SELECT id FROM clean_jobs LIMIT 2+1")

        self.assertFalse(result.valid)
        self.assertIn("LIMIT must be an integer literal", result.reason)

    def test_rejects_a_negative_limit(self) -> None:
        result = validate_sql("SELECT id FROM clean_jobs LIMIT -1")

        self.assertFalse(result.valid)
        self.assertIn("LIMIT must not be negative", result.reason)

    def test_a_non_literal_bound_inside_a_cte_is_part_of_the_cte(self) -> None:
        # Only the statement's own bound is the page. A bound inside a CTE is
        # that CTE's row count, and PostgreSQL can run it as written.
        result = validate_sql(
            "WITH newest AS (SELECT id FROM clean_jobs ORDER BY id LIMIT 2+1) "
            "SELECT id FROM newest ORDER BY id"
        )

        self.assertTrue(result.valid, result.reason)

    def test_rejects_a_fetch_with_ties(self) -> None:
        result = validate_sql(
            "SELECT id FROM clean_jobs ORDER BY id FETCH FIRST 3 ROWS WITH TIES"
        )

        self.assertFalse(result.valid)
        self.assertIn("WITH TIES", result.reason)

    def test_rejects_a_leading_semicolon(self) -> None:
        result = validate_sql("; SELECT id FROM clean_jobs")

        self.assertFalse(result.valid)
        self.assertIn("Multiple statements", result.reason)

    def test_rejects_a_table_statement(self) -> None:
        result = validate_sql("TABLE clean_jobs")

        self.assertFalse(result.valid)
        self.assertIn("Only SELECT statements are allowed", result.reason)

    def test_rejects_a_syntax_error_with_the_parser_message(self) -> None:
        result = validate_sql("SELECT id FROM clean_jobs WHERE")

        self.assertFalse(result.valid)
        self.assertIn("SQL syntax error", result.reason)

    def test_an_unterminated_literal_is_a_syntax_error(self) -> None:
        # The scanner raises before the parser runs; the failure still gets a
        # named reason instead of escaping as an internal error.
        result = validate_sql("SELECT 'unclosed")

        self.assertFalse(result.valid)
        self.assertIn("SQL syntax error", result.reason)

    def test_an_unterminated_comment_is_a_syntax_error(self) -> None:
        result = validate_sql("SELECT id FROM clean_jobs /* unclosed")

        self.assertFalse(result.valid)
        self.assertIn("SQL syntax error", result.reason)


class HiddenColumnTests(unittest.TestCase):
    def test_rejects_each_hidden_column(self) -> None:
        for column in sorted(HIDDEN_COLUMNS):
            with self.subTest(column=column):
                result = validate_sql(f"SELECT {column} FROM clean_jobs")

                self.assertFalse(result.valid)
                self.assertIn("Hidden column", result.reason)

    def test_rejects_hidden_column_in_filter(self) -> None:
        result = validate_sql("SELECT title FROM clean_jobs WHERE source = 'linkedin'")

        self.assertFalse(result.valid)
        self.assertIn("Hidden column", result.reason)

    def test_rejects_hidden_column_case_insensitively(self) -> None:
        result = validate_sql("SELECT EXTERNAL_ID FROM clean_jobs")

        self.assertFalse(result.valid)
        self.assertIn("Hidden column", result.reason)

    def test_rejects_quoted_hidden_column(self) -> None:
        result = validate_sql('SELECT "external_id" FROM clean_jobs')

        self.assertFalse(result.valid)
        self.assertIn("Hidden column", result.reason)

    def test_rejects_unicode_escaped_hidden_column(self) -> None:
        result = validate_sql('SELECT U&"external\\005fid" FROM clean_jobs')

        self.assertFalse(result.valid)
        self.assertIn("Hidden column", result.reason)

    def test_allows_hidden_column_name_inside_string_literal(self) -> None:
        result = validate_sql(
            "SELECT title FROM clean_jobs WHERE description ILIKE '%external_id%'"
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")

    def test_allows_visible_column_sharing_a_hidden_prefix(self) -> None:
        result = validate_sql("SELECT source_url FROM clean_jobs")

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "")


class HiddenColumnContractTests(unittest.TestCase):
    def test_hidden_columns_partition_the_physical_contract(self) -> None:
        from src.core.column_contract import (
            CONTRACT_COLUMN_NAMES,
            HIDDEN_COLUMN_NAMES,
        )

        prompt = yaml.safe_load(PROMPTS_PATH.read_text(encoding="utf-8"))["prompts"][
            "sql_generation"
        ]
        match = DECLARED_PATTERN.search(prompt)
        self.assertIsNotNone(match)
        declared = {column.strip() for column in match.group(1).split(",") if column.strip()}

        self.assertEqual(HIDDEN_COLUMNS, frozenset(HIDDEN_COLUMN_NAMES))
        self.assertEqual(HIDDEN_COLUMNS & declared, frozenset())
        self.assertEqual(HIDDEN_COLUMNS | declared, CONTRACT_COLUMN_NAMES)


class IdTiebreakTests(unittest.TestCase):
    """#727: a page boundary needs a total order, so ORDER BY includes id."""

    def test_rejects_a_query_without_an_order(self) -> None:
        self.assertFalse(has_id_tiebreak("SELECT id FROM clean_jobs"))

    def test_accepts_id_as_the_only_sort_key(self) -> None:
        self.assertTrue(has_id_tiebreak("SELECT id FROM clean_jobs ORDER BY id"))

    def test_accepts_id_after_another_sort_key(self) -> None:
        self.assertTrue(
            has_id_tiebreak(
                "SELECT id FROM clean_jobs"
                " ORDER BY created_on DESC NULLS LAST, id"
            )
        )

    def test_accepts_a_qualified_id(self) -> None:
        self.assertTrue(
            has_id_tiebreak(
                "SELECT c.id FROM clean_jobs AS c ORDER BY created_on, c.id"
            )
        )

    def test_accepts_a_quoted_id(self) -> None:
        self.assertTrue(
            has_id_tiebreak('SELECT id FROM clean_jobs ORDER BY "id" ASC')
        )

    def test_rejects_an_order_by_a_non_unique_column(self) -> None:
        # created_on has ties, so the page can move between calls without id.
        self.assertFalse(
            has_id_tiebreak(
                "SELECT id FROM clean_jobs ORDER BY created_on DESC NULLS LAST"
            )
        )

    def test_rejects_a_sort_key_that_merely_contains_id(self) -> None:
        self.assertFalse(
            has_id_tiebreak("SELECT id FROM clean_jobs ORDER BY order_id")
        )
        self.assertFalse(
            has_id_tiebreak("SELECT id FROM clean_jobs ORDER BY lower(id)")
        )

    def test_ignores_an_order_inside_a_subquery(self) -> None:
        # The inner ORDER BY does not order the rows the outer page slices.
        self.assertFalse(
            has_id_tiebreak(
                "SELECT id FROM (SELECT id FROM clean_jobs ORDER BY id) AS q"
            )
        )

    def test_ignores_an_order_inside_a_window(self) -> None:
        self.assertFalse(
            has_id_tiebreak(
                "SELECT row_number() OVER (ORDER BY id), id FROM clean_jobs"
            )
        )

    def test_ignores_order_by_text_inside_a_string_literal(self) -> None:
        self.assertFalse(
            has_id_tiebreak(
                "SELECT id FROM clean_jobs WHERE title = 'ORDER BY id'"
            )
        )

    def test_accepts_an_order_on_a_set_operation(self) -> None:
        self.assertTrue(
            has_id_tiebreak(
                "SELECT id FROM clean_jobs UNION SELECT id FROM clean_jobs ORDER BY id"
            )
        )

    def test_rejects_a_quoted_case_distinct_id(self) -> None:
        # Quoted identifiers keep their case, so "ID" is not the id column.
        self.assertFalse(has_id_tiebreak('SELECT id FROM clean_jobs ORDER BY "ID"'))

    def test_rejects_a_computed_id_key(self) -> None:
        self.assertFalse(has_id_tiebreak("SELECT id FROM clean_jobs ORDER BY id + 0"))

    def test_rejects_a_statement_the_guard_refuses(self) -> None:
        self.assertFalse(has_id_tiebreak("DELETE FROM clean_jobs"))

    def test_reads_the_order_up_to_the_bound_that_follows_it(self) -> None:
        self.assertTrue(
            has_id_tiebreak(
                "SELECT id FROM clean_jobs ORDER BY created_on, id LIMIT 5 OFFSET 20"
            )
        )

    def test_rejects_an_order_that_ends_at_the_bound_without_id(self) -> None:
        self.assertFalse(
            has_id_tiebreak(
                "SELECT id FROM clean_jobs ORDER BY created_on LIMIT 5 OFFSET 20"
            )
        )


if __name__ == "__main__":
    unittest.main()
