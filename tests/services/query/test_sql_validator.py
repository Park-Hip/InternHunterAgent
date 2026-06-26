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


if __name__ == "__main__":
    unittest.main()
