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
    assert_rejection_ratio,
    partition_by_row_quality,
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
    def test_leftover_is_active_column_is_tolerated(self, mock_session_factory: MagicMock) -> None:
        rows = [(name,) for name in _expected_columns() | {"is_active"}]
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


class PartitionByRowQualityTests(unittest.TestCase):
    def test_valid_jobs_all_accepted(self) -> None:
        jobs = [_make_job(external_id=f"job-{i}") for i in range(3)]

        accepted, violations = partition_by_row_quality(jobs)

        self.assertEqual(len(accepted), 3)
        self.assertEqual(violations, {})

    def test_empty_input(self) -> None:
        accepted, violations = partition_by_row_quality([])

        self.assertEqual(accepted, [])
        self.assertEqual(violations, {})

    # ---- one row per rule ----

    def test_blank_title_rejected_and_counted(self) -> None:
        accepted, violations = partition_by_row_quality([_make_job(title="")])

        self.assertEqual(accepted, [])
        self.assertEqual(violations, {"title_required": 1})

    def test_blank_company_rejected_and_counted(self) -> None:
        accepted, violations = partition_by_row_quality([_make_job(company="")])

        self.assertEqual(accepted, [])
        self.assertEqual(violations, {"company_required": 1})

    def test_non_finite_salary_rejected_and_counted(self) -> None:
        accepted, violations = partition_by_row_quality(
            [_make_job(salary_min=float("nan"))]
        )

        self.assertEqual(accepted, [])
        self.assertEqual(violations, {"salary_finite": 1})

    def test_inverted_salary_bounds_rejected_and_counted(self) -> None:
        accepted, violations = partition_by_row_quality(
            [_make_job(salary_min=3000.0, salary_max=2000.0)]
        )

        self.assertEqual(accepted, [])
        self.assertEqual(violations, {"salary_bounds": 1})

    def test_expiry_before_posted_rejected_and_counted(self) -> None:
        accepted, violations = partition_by_row_quality(
            [_make_job(posted_date=date(2026, 7, 1), listing_expires_on=date(2026, 6, 30))]
        )

        self.assertEqual(accepted, [])
        self.assertEqual(violations, {"expiry_after_posted": 1})

    # ---- multi-rule and multi-row ----

    def test_blank_title_and_inverted_salary_rejected_once_counted_twice(self) -> None:
        accepted, violations = partition_by_row_quality(
            [_make_job(title="", salary_min=3000.0, salary_max=2000.0)]
        )

        self.assertEqual(accepted, [])
        self.assertEqual(violations, {"title_required": 1, "salary_bounds": 1})

    def test_non_finite_salary_bounds_on_separate_rows(self) -> None:
        jobs = [
            _make_job(external_id="a", salary_min=float("nan")),
            _make_job(external_id="b", salary_max=float("inf")),
        ]

        accepted, violations = partition_by_row_quality(jobs)

        self.assertEqual(accepted, [])
        self.assertEqual(violations, {"salary_finite": 2})

    def test_both_non_finite_bounds_counted_once_per_row(self) -> None:
        accepted, violations = partition_by_row_quality(
            [_make_job(salary_min=float("nan"), salary_max=float("inf"))]
        )

        self.assertEqual(accepted, [])
        self.assertEqual(violations, {"salary_finite": 1})


class AssertRejectionRatioTests(unittest.TestCase):
    def test_zero_fetched_does_not_raise(self) -> None:
        assert_rejection_ratio(0, 0, 0.1)

    def test_exactly_at_ratio_does_not_raise(self) -> None:
        assert_rejection_ratio(2, 20, 0.1)

    def test_above_ratio_raises(self) -> None:
        with self.assertRaises(IngestionSafetyError):
            assert_rejection_ratio(3, 20, 0.1)


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
