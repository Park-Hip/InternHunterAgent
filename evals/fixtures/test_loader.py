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
        patch("evals.fixtures.loader._fixture_database_url", return_value=fixture_dsn),
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
