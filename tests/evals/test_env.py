"""Offline tests for evals.env: fixture environment binding.

No network calls, no provider credentials. Tests assert that
bind_fixture_environment sets the expected environment variables.
"""

from __future__ import annotations

import os
import pytest
from sqlalchemy.engine import make_url

from evals.env import bind_fixture_environment
from evals.fixtures.loader import fixture_database_url, fixture_reader_database_url


class TestBindFixtureEnvironment:
    def test_sets_the_owner_and_reader_dsns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "original")
        monkeypatch.setenv("AGENT_DATABASE_URL", "original-agent")
        bind_fixture_environment()
        # Loading keeps the owner; the tool path must use the restricted reader.
        assert os.environ["DATABASE_URL"] == fixture_database_url()
        assert os.environ["AGENT_DATABASE_URL"] == fixture_reader_database_url()

    def test_the_reader_is_a_non_owner_role_on_the_same_database(self) -> None:
        owner = make_url(fixture_database_url())
        reader = make_url(fixture_reader_database_url())
        assert reader.username != owner.username
        assert (reader.host or "localhost", reader.port or 5432, reader.database) == (
            owner.host or "localhost",
            owner.port or 5432,
            owner.database,
        )

    def test_a_reader_that_names_the_owner_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pointing the agent DSN back at the owner is the exact bug #730 fixes."""
        import evals.fixtures.loader as loader

        owner_url = fixture_database_url()
        monkeypatch.setattr(
            loader,
            "_fixture_config",
            lambda: {
                "database_url": owner_url,
                "reader_database_url": owner_url,
            },
        )
        with pytest.raises(ValueError, match="non-owner role"):
            fixture_reader_database_url()
