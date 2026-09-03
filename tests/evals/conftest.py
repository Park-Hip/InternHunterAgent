"""Contain the fixture-database bind that importing the driver performs.

``evals/driver.py`` binds both database URLs to the fixture DSN at import time,
and that is deliberate: the driver has to redirect the agent before ``src.core``
constructs anything from the serving DSN. Importing it from a test module makes
the bind a side effect of *collection*, though, so it would otherwise outlive
this directory and point the rest of the suite at the fixture database.
"""

from __future__ import annotations

import os
import pytest

from evals.fixtures.loader import fixture_database_url


_ORIGINAL_DATABASE_URL = os.environ.get("DATABASE_URL")
_ORIGINAL_AGENT_DATABASE_URL = os.environ.get("AGENT_DATABASE_URL")


def _restore_environment(name: str, original: str | None) -> None:
    if original is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = original


def _reset_database_caches() -> None:
    import sys

    config = sys.modules.get("src.core.config")
    if config is not None:
        config._settings_cache = None

    db = sys.modules.get("src.core.db")
    if db is None:
        return
    for engine_name in ("_engine", "_agent_engine"):
        engine = getattr(db, engine_name)
        if engine is not None:
            engine.dispose()
        setattr(db, engine_name, None)
    db._session_factory = None
    db._agent_session_factory = None


def pytest_collection_finish(session: object) -> None:
    """Restore database settings after every test module has been imported."""
    _restore_environment("DATABASE_URL", _ORIGINAL_DATABASE_URL)
    _restore_environment("AGENT_DATABASE_URL", _ORIGINAL_AGENT_DATABASE_URL)
    _reset_database_caches()


@pytest.fixture(autouse=True)
def fixture_database_environment() -> None:
    fixture_url = fixture_database_url()
    os.environ["DATABASE_URL"] = fixture_url
    os.environ["AGENT_DATABASE_URL"] = fixture_url
    _reset_database_caches()
    yield
    _restore_environment("DATABASE_URL", _ORIGINAL_DATABASE_URL)
    _restore_environment("AGENT_DATABASE_URL", _ORIGINAL_AGENT_DATABASE_URL)
    _reset_database_caches()
