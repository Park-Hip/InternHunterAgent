import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import httpx
from sqlalchemy.exc import DBAPIError, OperationalError

from src.services.ingestion.models import CleanJob, NormalizedJob
from src.services.ingestion.safety import (
    IngestionSafetyError,
    assert_clean_jobs_schema,
    assert_min_yield,
    assert_normalized_row_quality,
    send_dead_man_ping,
)


def _expected_columns() -> set[str]:
    return {c.name for c in CleanJob.__table__.columns}


def _mock_session(mock_session_factory: MagicMock, rows: list[tuple[str]]) -> MagicMock:
    session = mock_session_factory.return_value
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    session.execute.return_value = rows
    return session


class AssertCleanJobsSchemaTests(unittest.TestCase):
    @patch("src.services.ingestion.safety.session_factory")
    def test_matching_columns_do_not_raise(self, mock_session_factory: MagicMock) -> None:
        rows = [(name,) for name in _expected_columns()]
        _mock_session(mock_session_factory, rows)

        assert_clean_jobs_schema()

    @patch("src.services.ingestion.safety.session_factory")
    def test_missing_column_raises_and_names_it(self, mock_session_factory: MagicMock) -> None:
        columns = _expected_columns() - {"location"}
        rows = [(name,) for name in columns]
        _mock_session(mock_session_factory, rows)

        with self.assertRaises(IngestionSafetyError) as ctx:
            assert_clean_jobs_schema()

        self.assertIn("location", str(ctx.exception))

    @patch("src.services.ingestion.safety.session_factory")
    def test_unexpected_extra_column_raises_and_names_it(self, mock_session_factory: MagicMock) -> None:
        columns = _expected_columns() | {"location_old"}
        rows = [(name,) for name in columns]
        _mock_session(mock_session_factory, rows)

        with self.assertRaises(IngestionSafetyError) as ctx:
            assert_clean_jobs_schema()

        self.assertIn("location_old", str(ctx.exception))

    @patch("src.services.ingestion.safety.session_factory")
    def test_empty_result_raises_table_missing_message(self, mock_session_factory: MagicMock) -> None:
        _mock_session(mock_session_factory, [])

        with self.assertRaises(IngestionSafetyError) as ctx:
            assert_clean_jobs_schema()

        message = str(ctx.exception)
        self.assertIn("not found", message.lower())

    @patch("src.services.ingestion.safety.session_factory")
    def test_operational_error_raises_ingestion_safety_error(self, mock_session_factory: MagicMock) -> None:
        session = mock_session_factory.return_value
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        session.execute.side_effect = OperationalError("select", {}, Exception("connection lost"))

        with self.assertRaises(IngestionSafetyError):
            assert_clean_jobs_schema()

    @patch("src.services.ingestion.safety.session_factory")
    def test_dbapi_error_raises_ingestion_safety_error(self, mock_session_factory: MagicMock) -> None:
        session = mock_session_factory.return_value
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        session.execute.side_effect = DBAPIError("select", {}, Exception("db failure"))

        with self.assertRaises(IngestionSafetyError):
            assert_clean_jobs_schema()


class AssertMinYieldTests(unittest.TestCase):
    def test_under_floor_raises_with_both_numbers(self) -> None:
        with self.assertRaises(IngestionSafetyError) as ctx:
            assert_min_yield(3, 20)

        message = str(ctx.exception)
        self.assertIn("3", message)
        self.assertIn("20", message)

    def test_at_or_above_floor_does_not_raise(self) -> None:
        assert_min_yield(50, 20)


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
        "location": "Ho Chi Minh City",
        "posted_date": date(2026, 1, 1),
        "listing_expires_on": date(2026, 6, 30),
        "created_on": date(2025, 12, 1),
        "is_internship": True,
        "salary_min": 1500.0,
        "salary_max": 2500.0,
        "salary_currency": "USD",
        "is_salary_negotiable": False,
    }
    return NormalizedJob(**{**defaults, **overrides})


class AssertNormalizedRowQualityTests(unittest.TestCase):
    def test_valid_jobs_do_not_raise(self) -> None:
        jobs = [_make_job(external_id=f"job-{i}") for i in range(3)]

        assert_normalized_row_quality(jobs)

    def test_empty_iterable_does_not_raise(self) -> None:
        assert_normalized_row_quality([])

    # ---- title / company required ----

    def test_empty_title_raises_title_required(self) -> None:
        with self.assertRaises(IngestionSafetyError) as ctx:
            assert_normalized_row_quality([_make_job(title="")])

        self.assertIn("title_required=1", str(ctx.exception))

    def test_whitespace_title_raises_title_required(self) -> None:
        with self.assertRaises(IngestionSafetyError):
            assert_normalized_row_quality([_make_job(title="   ")])

    def test_empty_company_raises_company_required(self) -> None:
        with self.assertRaises(IngestionSafetyError) as ctx:
            assert_normalized_row_quality([_make_job(company="")])

        self.assertIn("company_required=1", str(ctx.exception))

    def test_whitespace_company_raises_company_required(self) -> None:
        with self.assertRaises(IngestionSafetyError):
            assert_normalized_row_quality([_make_job(company="\t ")])

    # ---- salary bounds ----

    def test_inverted_salary_bounds_raise(self) -> None:
        with self.assertRaises(IngestionSafetyError) as ctx:
            assert_normalized_row_quality([_make_job(salary_min=3000.0, salary_max=2000.0)])

        self.assertIn("salary_bounds=1", str(ctx.exception))

    def test_equal_salary_bounds_pass(self) -> None:
        assert_normalized_row_quality([_make_job(salary_min=2000.0, salary_max=2000.0)])

    def test_ordered_salary_bounds_pass(self) -> None:
        assert_normalized_row_quality([_make_job(salary_min=2000.0, salary_max=3000.0)])

    def test_single_sided_salary_passes(self) -> None:
        assert_normalized_row_quality(
            [
                _make_job(salary_min=2000.0, salary_max=None),
                _make_job(salary_min=None, salary_max=3000.0),
            ]
        )

    # ---- posted / expiry coherence ----

    def test_expiry_before_posted_raises(self) -> None:
        with self.assertRaises(IngestionSafetyError) as ctx:
            assert_normalized_row_quality(
                [_make_job(posted_date=date(2026, 7, 1), listing_expires_on=date(2026, 6, 30))]
            )

        self.assertIn("expiry_after_posted=1", str(ctx.exception))

    def test_expiry_after_posted_passes(self) -> None:
        assert_normalized_row_quality(
            [_make_job(posted_date=date(2026, 1, 1), listing_expires_on=date(2026, 6, 30))]
        )

    def test_expiry_equal_to_posted_passes(self) -> None:
        assert_normalized_row_quality(
            [_make_job(posted_date=date(2026, 6, 30), listing_expires_on=date(2026, 6, 30))]
        )

    def test_missing_posted_date_passes(self) -> None:
        assert_normalized_row_quality([_make_job(posted_date=None)])

    def test_missing_expiry_passes(self) -> None:
        assert_normalized_row_quality([_make_job(listing_expires_on=None)])

    # ---- failure reporting is aggregate and PII-free ----

    def test_violation_message_names_counts_not_identifiers(self) -> None:
        job = _make_job(
            external_id="secret-id-42",
            title="",
            company="   ",
            salary_min=4000.0,
            salary_max=1000.0,
        )

        with self.assertRaises(IngestionSafetyError) as ctx:
            assert_normalized_row_quality([job])

        message = str(ctx.exception)
        self.assertIn("title_required=1", message)
        self.assertIn("company_required=1", message)
        self.assertIn("salary_bounds=1", message)
        self.assertNotIn("secret-id-42", message)

    def test_multiple_violations_across_rows_are_counted(self) -> None:
        jobs = [
            _make_job(external_id="a", title=""),
            _make_job(external_id="b", title=" "),
            _make_job(external_id="c", company=""),
        ]

        with self.assertRaises(IngestionSafetyError) as ctx:
            assert_normalized_row_quality(jobs)

        self.assertIn("title_required=2", str(ctx.exception))
        self.assertIn("company_required=1", str(ctx.exception))


class SendDeadManPingTests(unittest.TestCase):
    @patch("src.services.ingestion.safety.httpx.post")
    def test_none_url_skips_without_http_call(self, mock_post: MagicMock) -> None:
        result = send_dead_man_ping(None)

        self.assertFalse(result)
        mock_post.assert_not_called()

    @patch("src.services.ingestion.safety.httpx.post")
    def test_empty_url_skips_without_http_call(self, mock_post: MagicMock) -> None:
        result = send_dead_man_ping("")

        self.assertFalse(result)
        mock_post.assert_not_called()

    @patch("src.services.ingestion.safety.httpx.post")
    def test_success_returns_true_and_posts_once(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(raise_for_status=MagicMock())

        result = send_dead_man_ping("https://hc-ping.com/abc")

        self.assertTrue(result)
        mock_post.assert_called_once_with("https://hc-ping.com/abc", timeout=10)

    @patch("src.services.ingestion.safety.httpx.post")
    def test_http_error_returns_false_without_raising(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = httpx.HTTPError("boom")

        result = send_dead_man_ping("https://hc-ping.com/abc")

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
