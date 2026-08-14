"""Point the agent at the fixture database, for the live eval tests only.

The tests left in this directory are the two that call a provider, and they must
run against the frozen fixture rather than the serving database. Everything they
touch resolves lazily: ``src/core/config.py`` exposes ``settings`` as a proxy that
constructs ``Settings()`` on first attribute access, and ``src/core/db.py`` builds
its engine and session factory on first use. So the redirect only has to be in
place before a test body runs, not before this module is imported.

That distinction is the point. This file used to write ``os.environ`` at import
time, which meant collecting these two modules redirected ``DATABASE_URL`` for
every test in the session, including the ones under ``tests/`` that have nothing
to do with the fixture. The autouse fixture below applies the redirect during the
setup of a test in this directory and undoes it afterwards.

Clearing the two caches is what makes the redirect effective rather than
decorative: if an earlier test has already read ``settings.DATABASE_URL`` or
opened the engine, the cached objects hold the serving database and setting the
environment variable would change nothing.
"""

from __future__ import annotations

import pytest

from evals.fixtures.loader import fixture_database_url


@pytest.fixture(autouse=True)
def use_fixture_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bind DATABASE_URL, and the objects derived from it, to the fixture database."""
    import src.core.config as config
    import src.core.db as db

    monkeypatch.setenv("DATABASE_URL", fixture_database_url())
    monkeypatch.setattr(config, "_settings_cache", None)
    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "_session_factory", None)
