"""Bind the fixture database before any ``src`` import freezes ``Settings()``.

The SQL guard gate calls this before importing any production module.
Settings cache database URLs on first access, so a late bind could point a
measurement at the serving database instead of the frozen fixture.

The serving DSN stays on the fixture owner, which is also what the loader uses
to build and seed the schema. The agent DSN is the fixture reader role, whose
column grants mirror production's ``internhunter_agent`` boundary (#730).
"""

from __future__ import annotations

import os

from evals.fixtures.loader import fixture_database_url, fixture_reader_database_url


def bind_fixture_environment() -> None:
    """Set the two database URLs before any ``src`` import.

    Call before any production import or Settings access.
    """
    os.environ["DATABASE_URL"] = fixture_database_url()
    os.environ["AGENT_DATABASE_URL"] = fixture_reader_database_url()
