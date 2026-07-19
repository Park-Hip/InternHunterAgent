import unittest
from unittest.mock import MagicMock, patch

import httpx
from sqlalchemy.exc import DBAPIError, OperationalError

from src.services.ingestion.models import CleanJob
from src.services.ingestion.safety import (
    IngestionSafetyError,
    assert_clean_jobs_schema,
    assert_min_yield,
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
