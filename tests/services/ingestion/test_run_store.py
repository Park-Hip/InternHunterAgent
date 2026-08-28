import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

from src.services.ingestion.models import IngestionRun, IngestionRunSummary
from src.services.ingestion.run_store import persist_ingestion_run


def _summary(**overrides) -> IngestionRunSummary:
    defaults = {
        "source": "vietnamworks",
        "started_at": datetime(2026, 8, 28, 8, 0, tzinfo=UTC),
        "finished_at": datetime(2026, 8, 28, 8, 1, tzinfo=UTC),
        "outcome": "completed",
        "fetched": 3,
        "raw_upserted": 3,
        "raw_new": 1,
        "raw_changed": 1,
        "raw_unchanged": 1,
        "clean_loaded": 3,
        "skipped": 0,
        "expired_count": 0,
        "pages_failed": 0,
    }
    return IngestionRunSummary(**{**defaults, **overrides})


def _mock_session(mock_session_factory: MagicMock) -> MagicMock:
    session = mock_session_factory.return_value
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    return session


class PersistIngestionRunTests(unittest.TestCase):
    @patch("src.services.ingestion.run_store.session_factory")
    def test_completed_summary_is_appended_with_counters(
        self, mock_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_session_factory)

        self.assertTrue(persist_ingestion_run(_summary()))

        row = session.add.call_args.args[0]
        self.assertIsInstance(row, IngestionRun)
        self.assertEqual(row.outcome, "completed")
        self.assertEqual(row.raw_new, 1)
        self.assertIsNone(row.failure_phase)
        session.commit.assert_called_once()

    @patch("src.services.ingestion.run_store.session_factory")
    def test_safety_abort_preserves_only_known_metrics(
        self, mock_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_session_factory)

        persist_ingestion_run(
            _summary(
                outcome="safety_aborted",
                failure_phase="yield_check",
                failure_code="safety_check_failed",
                clean_loaded=None,
                skipped=None,
                expired_count=None,
            )
        )

        row = session.add.call_args.args[0]
        self.assertEqual(row.outcome, "safety_aborted")
        self.assertEqual(row.failure_phase, "yield_check")
        self.assertIsNone(row.clean_loaded)
        self.assertIsNone(row.skipped)
        self.assertIsNone(row.expired_count)

    @patch("src.services.ingestion.run_store.session_factory")
    def test_runtime_failure_preserves_unknown_metrics_as_null(
        self, mock_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_session_factory)

        persist_ingestion_run(
            _summary(
                outcome="failed",
                failure_phase="raw_upsert",
                failure_code="unexpected_error",
                raw_upserted=None,
                raw_new=None,
                raw_changed=None,
                raw_unchanged=None,
                clean_loaded=None,
                skipped=None,
                expired_count=None,
            )
        )

        row = session.add.call_args.args[0]
        self.assertEqual(row.outcome, "failed")
        self.assertEqual(row.failure_code, "unexpected_error")
        self.assertIsNone(row.raw_upserted)
        self.assertIsNone(row.clean_loaded)

    @patch("src.services.ingestion.run_store.session_factory")
    def test_each_attempt_uses_a_new_insert(
        self, mock_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_session_factory)

        persist_ingestion_run(_summary())
        persist_ingestion_run(_summary())

        self.assertEqual(session.add.call_count, 2)
        first, second = (call.args[0] for call in session.add.call_args_list)
        self.assertIsNot(first, second)
        self.assertEqual(session.commit.call_count, 2)

    @patch("src.services.ingestion.run_store.session_factory")
    def test_persistence_failure_does_not_raise(
        self, mock_session_factory: MagicMock
    ) -> None:
        session = _mock_session(mock_session_factory)
        session.commit.side_effect = OperationalError(
            "insert", {}, Exception("unavailable")
        )

        self.assertFalse(persist_ingestion_run(_summary(outcome="failed")))
