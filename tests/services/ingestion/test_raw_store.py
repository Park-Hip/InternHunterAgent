import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import DBAPIError, OperationalError

from src.services.ingestion.models import RawPosting
from src.services.ingestion.raw_store import RawStoreError, RawUpsertCounts, upsert_raw_postings


def _make_posting(**overrides) -> RawPosting:
    defaults = {
        "source": "vietnamworks",
        "external_id": "job-001",
        "source_url": "https://example.com/job/1",
        "raw_payload": {"title": "Intern"},
        "content_hash": "abc123",
    }
    return RawPosting(**{**defaults, **overrides})


def _mock_session(mock_session_factory: MagicMock) -> MagicMock:
    session = mock_session_factory.return_value
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    return session


class UpsertRawPostingsTests(unittest.TestCase):
    @patch("src.services.ingestion.raw_store.session_factory")
    def test_empty_input_returns_zero_without_hitting_db(self, mock_session_factory: MagicMock) -> None:
        counts = upsert_raw_postings([])
        self.assertEqual(counts, RawUpsertCounts(new=0, changed=0, unchanged=0))
        mock_session_factory.assert_not_called()

    @patch("src.services.ingestion.raw_store.session_factory")
    def test_classifies_missing_natural_keys_as_new(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.return_value.all.return_value = []
        postings = [_make_posting(external_id=f"job-{i}") for i in range(3)]

        counts = upsert_raw_postings(postings)

        self.assertEqual(counts, RawUpsertCounts(new=3, changed=0, unchanged=0))
        self.assertEqual(counts.total, 3)

    @patch("src.services.ingestion.raw_store.session_factory")
    def test_classifies_existing_hashes_as_changed_or_unchanged(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        existing = MagicMock()
        existing.all.return_value = [
            ("vietnamworks", "unchanged", "same-hash"),
            ("vietnamworks", "changed", "old-hash"),
        ]
        session.execute.side_effect = [existing, MagicMock()]
        postings = [
            _make_posting(external_id="new", content_hash="new-hash"),
            _make_posting(external_id="unchanged", content_hash="same-hash"),
            _make_posting(external_id="changed", content_hash="new-hash"),
        ]

        counts = upsert_raw_postings(postings)

        self.assertEqual(counts, RawUpsertCounts(new=1, changed=1, unchanged=1))

    @patch("src.services.ingestion.raw_store.session_factory")
    def test_repeat_run_is_classified_as_unchanged(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        existing = MagicMock()
        existing.all.return_value = [("vietnamworks", "job-001", "abc123")]
        session.execute.side_effect = [existing, MagicMock()]

        counts = upsert_raw_postings([_make_posting()])

        self.assertEqual(counts, RawUpsertCounts(new=0, changed=0, unchanged=1))

    @patch("src.services.ingestion.raw_store.session_factory")
    def test_executes_insert_on_conflict_do_update_statement(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        postings = [_make_posting()]
        upsert_raw_postings(postings)

        self.assertEqual(session.execute.call_count, 2)
        stmt = session.execute.call_args.args[0]
        compiled = stmt.compile(dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect())
        sql_text = str(compiled)
        self.assertIn("ON CONFLICT", sql_text.upper())
        self.assertIn("DO UPDATE", sql_text.upper())

    @patch("src.services.ingestion.raw_store.session_factory")
    def test_conflict_target_includes_source_and_external_id(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        postings = [_make_posting()]
        upsert_raw_postings(postings)

        stmt = session.execute.call_args.args[0]
        compiled = stmt.compile(dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect())
        sql_text = str(compiled)
        self.assertIn("source", sql_text)
        self.assertIn("external_id", sql_text)

    @patch("src.services.ingestion.raw_store.session_factory")
    def test_reads_existing_hashes_using_natural_keys(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.return_value.all.return_value = []

        upsert_raw_postings([_make_posting()])

        select_stmt = session.execute.call_args_list[0].args[0]
        compiled = select_stmt.compile(dialect=__import__("sqlalchemy.dialects.postgresql", fromlist=["dialect"]).dialect())
        sql_text = str(compiled)
        self.assertIn("content_hash", sql_text)
        self.assertIn("source", sql_text)
        self.assertIn("external_id", sql_text)

    @patch("src.services.ingestion.raw_store.session_factory")
    def test_commit_called_on_success(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        upsert_raw_postings([_make_posting()])
        session.commit.assert_called_once()

    @patch("src.services.ingestion.raw_store.session_factory")
    def test_session_context_exited_on_success(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        upsert_raw_postings([_make_posting()])
        session.__exit__.assert_called_once()

    @patch("src.services.ingestion.raw_store.session_factory")
    def test_operational_error_raises_raw_store_error(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.side_effect = OperationalError("insert", {}, Exception("connection lost"))

        with self.assertRaises(RawStoreError):
            upsert_raw_postings([_make_posting()])

    @patch("src.services.ingestion.raw_store.session_factory")
    def test_dbapi_error_raises_raw_store_error(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.side_effect = DBAPIError("insert", {}, Exception("db failure"))

        with self.assertRaises(RawStoreError):
            upsert_raw_postings([_make_posting()])

    @patch("src.services.ingestion.raw_store.session_factory")
    def test_session_context_exited_on_failure(self, mock_session_factory: MagicMock) -> None:
        session = _mock_session(mock_session_factory)
        session.execute.side_effect = OperationalError("insert", {}, Exception("boom"))

        with self.assertRaises(RawStoreError):
            upsert_raw_postings([_make_posting()])

        session.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
