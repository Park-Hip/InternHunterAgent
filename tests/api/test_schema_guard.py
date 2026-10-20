import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

from src.api.schema_guard import SchemaGuardError, assert_serving_schema
from src.core.column_contract import HIDDEN_COLUMN_NAMES, VISIBLE_COLUMN_TYPES


def _contract_rows() -> list[tuple[str, str]]:
    """The physical table: the guard's 16 typed columns plus the hidden five."""
    rows = list(VISIBLE_COLUMN_TYPES.items())
    rows.extend((column, "text") for column in HIDDEN_COLUMN_NAMES)
    return rows


def _mock_session(
    mock_session_factory: MagicMock, rows: list[tuple[str, str]]
) -> MagicMock:
    session = mock_session_factory.return_value
    session.__enter__.return_value = session
    session.__exit__.return_value = False
    session.execute.return_value = rows
    return session


class AssertServingSchemaTests(unittest.TestCase):
    @patch("src.api.schema_guard.session_factory")
    def test_matching_columns_do_not_raise(
        self, mock_session_factory: MagicMock
    ) -> None:
        _mock_session(mock_session_factory, _contract_rows())

        assert_serving_schema()

    @patch("src.api.schema_guard.session_factory")
    def test_an_extra_physical_column_does_not_raise(
        self, mock_session_factory: MagicMock
    ) -> None:
        """A migration may add a column before the release that knows about it.

        The grant keeps it invisible to the agent, so boot must not depend on
        every running process already having a matching literal.
        """
        rows = _contract_rows() + [("work_mode", "text")]
        _mock_session(mock_session_factory, rows)

        assert_serving_schema()

    @patch("src.api.schema_guard.logger")
    @patch("src.api.schema_guard.session_factory")
    def test_an_extra_physical_column_is_logged(
        self, mock_session_factory: MagicMock, mock_logger: MagicMock
    ) -> None:
        rows = _contract_rows() + [("work_mode", "text")]
        _mock_session(mock_session_factory, rows)

        assert_serving_schema()

        events = [call.args[0] for call in mock_logger.info.call_args_list]
        self.assertIn("api.schema_extra_columns", events)
        extra_call = next(
            call
            for call in mock_logger.info.call_args_list
            if call.args[0] == "api.schema_extra_columns"
        )
        self.assertEqual(extra_call.kwargs["columns"], ["work_mode"])

    @patch("src.api.schema_guard.session_factory")
    def test_missing_column_raises_and_names_it(
        self, mock_session_factory: MagicMock
    ) -> None:
        rows = [(name, sql_type) for name, sql_type in _contract_rows() if name != "location"]
        _mock_session(mock_session_factory, rows)

        with self.assertRaises(SchemaGuardError) as ctx:
            assert_serving_schema()

        message = str(ctx.exception)
        self.assertIn("location", message)
        self.assertIn("missing", message)

    @patch("src.api.schema_guard.session_factory")
    def test_a_wrong_type_raises_and_names_both_types(
        self, mock_session_factory: MagicMock
    ) -> None:
        rows = [
            (name, "integer" if name == "location" else sql_type)
            for name, sql_type in _contract_rows()
        ]
        _mock_session(mock_session_factory, rows)

        with self.assertRaises(SchemaGuardError) as ctx:
            assert_serving_schema()

        message = str(ctx.exception)
        self.assertIn("location", message)
        self.assertIn("wrong_type", message)
        self.assertIn("text", message)
        self.assertIn("integer", message)

    @patch("src.api.schema_guard.session_factory")
    def test_renamed_column_fails_because_the_contract_column_is_missing(
        self, mock_session_factory: MagicMock
    ) -> None:
        """The old name is an ignored extra; the dropped name is the failure."""
        rows = [
            (name, sql_type)
            for name, sql_type in _contract_rows()
            if name != "location"
        ] + [("location_old", "text")]
        _mock_session(mock_session_factory, rows)

        with self.assertRaises(SchemaGuardError) as ctx:
            assert_serving_schema()

        message = str(ctx.exception)
        self.assertIn("location", message)
        self.assertNotIn("location_old", message)

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
        session.execute.side_effect = OperationalError(
            "select", {}, Exception("connection lost")
        )

        with self.assertRaises(SchemaGuardError) as ctx:
            assert_serving_schema()

        self.assertIn("Failed to inspect", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
