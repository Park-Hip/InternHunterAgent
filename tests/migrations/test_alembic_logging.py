"""An in-process upgrade must not silence the application's loggers.

Alembic's env runs `fileConfig` on every upgrade. With the default
`disable_existing_loggers=True`, every logger created before the upgrade is
switched off for the rest of the process - in this repository that includes
`api_gateway`, which evaluations and tests keep observing after the fixture
schema is rebuilt through `evals.fixtures.loader.load_fixture`. This runs the
real `alembic/env.py` against the fixture database and pins the fix.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from evals.fixtures.loader import (
    fixture_database_endpoint,
    fixture_database_reachable,
    fixture_database_url,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_an_in_process_upgrade_leaves_the_application_logger_enabled(
    monkeypatch,
) -> None:
    if not fixture_database_reachable():
        host, port = fixture_database_endpoint()
        pytest.skip(
            f"Fixture Postgres is not reachable at {host}:{port}; start it with "
            "`docker compose up -d postgres`."
        )

    logger = logging.getLogger("api_gateway")
    logger.disabled = False

    monkeypatch.setenv("ALEMBIC_DATABASE_URL", fixture_database_url())
    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    command.upgrade(alembic_cfg, "head")

    assert logger.disabled is False
