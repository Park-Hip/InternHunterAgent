import unittest

from src.services.query.sql_validator import validate_sql


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


if __name__ == "__main__":
    unittest.main()
