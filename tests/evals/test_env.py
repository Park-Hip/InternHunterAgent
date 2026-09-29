"""Offline tests for evals.env — fixture environment binding.

No network calls, no provider credentials. Tests that bind_fixture_environment
sets the expected environment variables.
"""

from __future__ import annotations

import os
import pytest

from evals.env import bind_fixture_environment


class TestBindFixtureEnvironment:
    def test_sets_database_urls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "original")
        monkeypatch.setenv("AGENT_DATABASE_URL", "original-agent")
        bind_fixture_environment()
        # The fixture URL replaces whatever was there.
        assert "postgresql+psycopg" in os.environ["DATABASE_URL"]
        assert "postgresql+psycopg" in os.environ["AGENT_DATABASE_URL"]

    def test_sets_tracing_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LANGFUSE_TRACING_ENVIRONMENT", raising=False)
        monkeypatch.delenv("LANGFUSE_ENABLED", raising=False)
        monkeypatch.delenv("LANGFUSE_RELEASE", raising=False)
        bind_fixture_environment()
        assert os.environ["LANGFUSE_TRACING_ENVIRONMENT"] == "evaluation"
        assert os.environ["LANGFUSE_ENABLED"] == "true"
        assert os.environ["LANGFUSE_RELEASE"] != ""

    def test_does_not_overwrite_existing_langfuse_release(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LANGFUSE_RELEASE", "my-release")
        bind_fixture_environment()
        assert os.environ["LANGFUSE_RELEASE"] == "my-release"
