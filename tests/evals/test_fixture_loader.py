import os
from unittest.mock import patch

from evals.fixtures import loader


def test_upgrade_schema_targets_fixture_database_and_restores_environment() -> None:
    fixture_dsn = "postgresql+psycopg://fixture-user:fixture-pass@localhost/fixture"
    original_url = os.environ.pop("ALEMBIC_DATABASE_URL", None)

    try:
        with patch("evals.fixtures.loader.command.upgrade") as upgrade:
            def assert_fixture_target(*_args) -> None:
                assert os.environ["ALEMBIC_DATABASE_URL"] == fixture_dsn

            upgrade.side_effect = assert_fixture_target
            loader._upgrade_schema(fixture_dsn)

        config, revision = upgrade.call_args.args
        assert config.get_main_option("script_location") == str(
            loader.REPO_ROOT / "alembic"
        )
        assert revision == "head"
        assert "ALEMBIC_DATABASE_URL" not in os.environ
    finally:
        if original_url is not None:
            os.environ["ALEMBIC_DATABASE_URL"] = original_url


def test_load_fixture_migrates_before_seeding() -> None:
    fixture_dsn = "postgresql+psycopg://fixture-user:fixture-pass@localhost/fixture"

    with (
        patch("evals.fixtures.loader.fixture_database_url", return_value=fixture_dsn),
        patch("evals.fixtures.loader._ensure_database_exists") as ensure_database,
        patch("evals.fixtures.loader._drop_fixture_schema") as drop_fixture_schema,
        patch("evals.fixtures.loader._upgrade_schema") as upgrade_schema,
        patch("evals.fixtures.loader._run_sql_file") as run_sql_file,
    ):
        loader.load_fixture()

    ensure_database.assert_called_once_with(fixture_dsn)
    drop_fixture_schema.assert_called_once_with(fixture_dsn)
    upgrade_schema.assert_called_once_with(fixture_dsn)
    run_sql_file.assert_called_once_with(fixture_dsn, loader.SEED_SQL_PATH)


def test_fixture_database_endpoint_parses_host_and_port() -> None:
    with patch(
        "evals.fixtures.loader.fixture_database_url",
        return_value="postgresql+psycopg://user:pass@localhost:5433/db",
    ):
        assert loader.fixture_database_endpoint() == ("localhost", 5433)


def test_fixture_database_endpoint_defaults_port_when_omitted() -> None:
    with patch(
        "evals.fixtures.loader.fixture_database_url",
        return_value="postgresql+psycopg://user:pass@localhost/db",
    ):
        assert loader.fixture_database_endpoint() == ("localhost", 5432)


def test_fixture_database_reachable_true_when_connect_succeeds() -> None:
    with (
        patch(
            "evals.fixtures.loader.fixture_database_url",
            return_value="postgresql+psycopg://user:pass@localhost:5433/db",
        ),
        patch("evals.fixtures.loader.socket.create_connection") as create,
    ):
        assert loader.fixture_database_reachable() is True
    create.assert_called_once_with(
        ("localhost", 5433), timeout=loader.FIXTURE_REACHABILITY_TIMEOUT_SECONDS
    )


def test_fixture_database_reachable_false_when_connect_is_refused() -> None:
    with patch(
        "evals.fixtures.loader.socket.create_connection",
        side_effect=ConnectionRefusedError,
    ):
        assert loader.fixture_database_reachable() is False
