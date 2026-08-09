import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

from src.api.schema_guard import (
    EXPECTED_COLUMNS,
    SchemaGuardError,
    assert_serving_schema,
)


def _mock_session(mock_session_factory: MagicMock, rows: list[tuple[str]]) -> MagicMock:
    session = mock_session_factory.return_value
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    session.execute.return_value = rows
    return session


class AssertServingSchemaTests(unittest.TestCase):
    @patch("src.api.schema_guard.session_factory")
    def test_matching_columns_do_not_raise(self, mock_session_factory: MagicMock) -> None:
        rows = [(name,) for name in EXPECTED_COLUMNS]
        _mock_session(mock_session_factory, rows)

        assert_serving_schema()

    @patch("src.api.schema_guard.session_factory")
    def test_missing_column_raises_and_names_it(self, mock_session_factory: MagicMock) -> None:
        columns = EXPECTED_COLUMNS - {"location"}
        rows = [(name,) for name in columns]
        _mock_session(mock_session_factory, rows)

        with self.assertRaises(SchemaGuardError) as ctx:
            assert_serving_schema()

        message = str(ctx.exception)
        self.assertIn("location", message)
        self.assertIn("missing", message)

    @patch("src.api.schema_guard.session_factory")
    def test_renamed_column_names_both_directions(self, mock_session_factory: MagicMock) -> None:
        columns = (EXPECTED_COLUMNS - {"location"}) | {"location_old"}
        rows = [(name,) for name in columns]
        _mock_session(mock_session_factory, rows)

        with self.assertRaises(SchemaGuardError) as ctx:
            assert_serving_schema()

        message = str(ctx.exception)
        self.assertIn("location", message)
        self.assertIn("location_old", message)

    @patch("src.api.schema_guard.session_factory")
    def test_unexpected_extra_column_raises_and_names_it(
        self, mock_session_factory: MagicMock
    ) -> None:
        columns = EXPECTED_COLUMNS | {"surprise_col"}
        rows = [(name,) for name in columns]
        _mock_session(mock_session_factory, rows)

        with self.assertRaises(SchemaGuardError) as ctx:
            assert_serving_schema()

        message = str(ctx.exception)
        self.assertIn("surprise_col", message)
        self.assertIn("unexpected", message)

    @patch("src.api.schema_guard.session_factory")
    def test_empty_result_raises_table_missing_message(
        self, mock_session_factory: MagicMock
    ) -> None:
        _mock_session(mock_session_factory, [])

        with self.assertRaises(SchemaGuardError) as ctx:
            assert_serving_schema()

        self.assertIn("not found", str(ctx.exception).lower())

    @patch("src.api.schema_guard.session_factory")
    def test_operational_error_raises_schema_guard_error(
        self, mock_session_factory: MagicMock
    ) -> None:
        session = mock_session_factory.return_value
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        session.execute.side_effect = OperationalError("select", {}, Exception("connection lost"))

        with self.assertRaises(SchemaGuardError) as ctx:
            assert_serving_schema()

        self.assertIn("Failed to inspect", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
