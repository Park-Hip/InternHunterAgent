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


if __name__ == "__main__":
    unittest.main()
