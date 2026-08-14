"""Contain the fixture-database bind that importing the driver performs.

``evals/driver.py`` binds ``DATABASE_URL`` to the fixture DSN at import time, and
that is deliberate: the driver has to redirect the agent before ``src.core``
constructs anything from the serving DSN. Importing it from a test module makes
the bind a side effect of *collection*, though, so it would otherwise outlive
this directory and point the rest of the suite at the fixture database.

No test here reads ``DATABASE_URL``. The ones that need the fixture ask
``evals.fixtures.loader.fixture_database_url()`` for it by name, so restoring the
environment once collection is done costs these tests nothing and leaves the
suite with the DSN it started with.
"""

from __future__ import annotations

import os


_ORIGINAL_DATABASE_URL = os.environ.get("DATABASE_URL")


def pytest_collection_finish(session: object) -> None:
    """Restore DATABASE_URL after every test module has been imported."""
    if _ORIGINAL_DATABASE_URL is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = _ORIGINAL_DATABASE_URL
