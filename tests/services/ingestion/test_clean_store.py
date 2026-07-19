import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import DBAPIError, OperationalError

from src.services.ingestion.clean_store import (
    CleanStoreError,
    expire_stale_clean_jobs,
    upsert_clean_jobs,
)
from src.services.ingestion.models import NormalizedJob


def _make_job(**overrides) -> NormalizedJob:
    defaults = {
        "source": "vietnamworks",
        "external_id": "job-001",
        "source_url": "https://example.com/job/1",
        "title": "Data Intern",
        "company": "Acme Corp",
        "role": "Data Science",
        "description": "Work with data",
        "tech_stack": "Python, SQL",
        "job_level": "Intern",
        "location": "Ho Chi Minh",
        "posted_date": date(2025, 1, 1),
        "is_internship": True,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "is_salary_negotiable": True,
    }
    return NormalizedJob(**{**defaults, **overrides})


def _mock_session(mock_session_factory: MagicMock) -> MagicMock:
    session = mock_session_factory.return_value
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    return session


class UpsertCleanJobsTests(unittest.TestCase):
    @patch("src.services.ingestion.clean_store.session_factory")
    def test_empty_input_returns_zero_without_hitting_db(self, mock_session_factory: MagicMock) -> None:
        count = upsert_clean_jobs([])
        self.assertEqual(count, 0)
        mock_session_factory.assert_not_called()

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_returns_count_equal_to_number_of_jobs(self, mock_session_factory: MagicMock) -> None:
        _mock_session(mock_session_factory)
        jobs = [_make_job(external_id=f"job-{i}") for i in range(3)]
        count = upsert_clean_jobs(jobs)
        self.assertEqual(count, 3)

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_intra_batch_duplicate_key_is_deduped_last_wins(self, mock_session_factory: MagicMock) -> None:
        # Same (source, external_id) twice would crash Postgres ON CONFLICT DO
        # UPDATE ("cannot affect row a second time"); dedup keeps the last row.
        session = _mock_session(mock_session_factory)
        jobs = [
            _make_job(external_id="dup", title="First"),
            _make_job(external_id="dup", title="Second"),
        ]
        count = upsert_clean_jobs(jobs)
        self.assertEqual(count, 1)

        insert_stmt = session.execute.call_args_list[0].args[0]
        compiled = insert_stmt.compile(
            dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect()
        )
        titles = [v for k, v in compiled.params.items() if k.startswith("title")]
        self.assertEqual(titles, ["Second"])

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_no_truncate_executed(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        upsert_clean_jobs([_make_job()])

        self.assertEqual(session.execute.call_count, 1)
        for call in session.execute.call_args_list:
            self.assertNotIn("TRUNCATE", str(call.args[0]).upper())

        insert_stmt = session.execute.call_args_list[0].args[0]
        compiled = insert_stmt.compile(
            dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect()
        )
        sql_text = str(compiled).upper()
        self.assertIn("ON CONFLICT", sql_text)
        self.assertIn("DO UPDATE", sql_text)

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_conflict_target_includes_source_and_external_id(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        upsert_clean_jobs([_make_job()])

        insert_stmt = session.execute.call_args_list[0].args[0]
        compiled = insert_stmt.compile(
            dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect()
        )
        sql_text = str(compiled)
        self.assertIn("source", sql_text)
        self.assertIn("external_id", sql_text)

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_upsert_refreshes_last_seen_and_is_active_but_not_first_seen(
        self, mock_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_session_factory)
        upsert_clean_jobs([_make_job()])

        insert_stmt = session.execute.call_args_list[0].args[0]
        compiled = insert_stmt.compile(
            dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect()
        )
        sql_text = str(compiled).upper()
        set_clause = sql_text.split("DO UPDATE SET", 1)[1]
        self.assertIn("LAST_SEEN_AT", set_clause)
        self.assertIn("IS_ACTIVE", set_clause)
        self.assertNotIn("FIRST_SEEN_AT", set_clause)

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_commit_called_once_on_success(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        upsert_clean_jobs([_make_job()])
        session.commit.assert_called_once()

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_session_context_exited_on_success(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        upsert_clean_jobs([_make_job()])
        session.__exit__.assert_called_once()

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_operational_error_raises_clean_store_error(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.side_effect = OperationalError("insert", {}, Exception("connection lost"))

        with self.assertRaises(CleanStoreError):
            upsert_clean_jobs([_make_job()])

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_dbapi_error_raises_clean_store_error(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.side_effect = DBAPIError("insert", {}, Exception("db failure"))

        with self.assertRaises(CleanStoreError):
            upsert_clean_jobs([_make_job()])

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_session_context_exited_on_failure(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.side_effect = OperationalError("insert", {}, Exception("boom"))

        with self.assertRaises(CleanStoreError):
            upsert_clean_jobs([_make_job()])

        session.__exit__.assert_called_once()


class ExpireStaleCleanJobsTests(unittest.TestCase):
    @patch("src.services.ingestion.clean_store.session_factory")
    def test_executes_time_based_update_never_delete(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.return_value.rowcount = 2

        count = expire_stale_clean_jobs(7)

        self.assertEqual(count, 2)
        stmt, params = session.execute.call_args.args
        sql_text = str(stmt).upper()
        self.assertIn("UPDATE CLEAN_JOBS", sql_text)
        self.assertIn("IS_ACTIVE = FALSE", sql_text)
        self.assertNotIn("DELETE", sql_text)
        self.assertEqual(params, {"days": 7})

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_commit_called_once_on_success(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.return_value.rowcount = 0
        expire_stale_clean_jobs(7)
        session.commit.assert_called_once()

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_operational_error_raises_clean_store_error(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.side_effect = OperationalError("expire", {}, Exception("connection lost"))

        with self.assertRaises(CleanStoreError):
            expire_stale_clean_jobs(7)

    @patch("src.services.ingestion.clean_store.session_factory")
    def test_dbapi_error_raises_clean_store_error(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.side_effect = DBAPIError("expire", {}, Exception("db failure"))

        with self.assertRaises(CleanStoreError):
            expire_stale_clean_jobs(7)


if __name__ == "__main__":
    unittest.main()
