from __future__ import annotations

import psycopg
import pytest
from sqlalchemy.exc import OperationalError

from src.core import db as db_module
from src.core.db import agent_session_factory, engine, session_factory


class _StubSettings:
    """A settings-shaped stand-in so the tests never touch the real DSNs.

    The writer DSN carries its own connect_timeout on purpose: the engine must
    still use the configured bound (issue #642).
    """

    DATABASE_URL = "postgresql+psycopg://writer:pw@writer-host:5432/app?connect_timeout=300"
    AGENT_DATABASE_URL = "postgresql+psycopg://agent:pw@agent-host:5432/app"
    config_yaml = {"database": {"connect_timeout_seconds": 4}}


def test_db_exports_engine_and_session_factory() -> None:
    assert engine is not None
    assert session_factory is not None
    assert session_factory.kw["bind"] is not None
    assert session_factory.kw["bind"].url == engine.url


def test_engine_does_not_connect_on_import() -> None:
    # Importing the module should not require a live Postgres instance.
    assert engine.url.render_as_string(hide_password=False).startswith("postgresql+psycopg://")


def test_db_exports_agent_session_factory() -> None:
    assert agent_session_factory is not None
    assert agent_session_factory.kw["bind"] is not None


def test_agent_session_factory_uses_different_url_than_writer() -> None:
    # The agent-read factory must bind to AGENT_DATABASE_URL, not DATABASE_URL.
    writer_url = str(session_factory.kw["bind"].url)
    agent_url = str(agent_session_factory.kw["bind"].url)
    assert writer_url != agent_url
    # Each URL must carry its own driver prefix; the concrete username/host
    # vary across environments (local, CI, integration), so only assert the
    # structural guarantee that they differ.
    assert "+psycopg://" in writer_url
    assert "+psycopg://" in agent_url


def test_connect_timeout_reads_the_configured_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_module, "settings", _StubSettings())

    assert db_module.connect_timeout_seconds() == 4


def test_connect_timeout_falls_back_to_a_bounded_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _NoDatabaseSection(_StubSettings):
        config_yaml: dict = {}

    monkeypatch.setattr(db_module, "settings", _NoDatabaseSection())

    assert db_module.DEFAULT_CONNECT_TIMEOUT_SECONDS > 0
    assert (
        db_module.connect_timeout_seconds() == db_module.DEFAULT_CONNECT_TIMEOUT_SECONDS
    )


def test_both_engines_enforce_the_bound_over_the_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[dict] = []

    def fake_connect(*args, **kwargs):
        recorded.append(kwargs)
        raise psycopg.OperationalError("simulated unreachable database")

    monkeypatch.setattr(db_module, "settings", _StubSettings())
    monkeypatch.setattr(psycopg, "connect", fake_connect)
    monkeypatch.setattr(db_module, "_engine", None)
    monkeypatch.setattr(db_module, "_agent_engine", None)

    for build in (db_module._get_engine, db_module._get_agent_engine):
        built = build()
        try:
            with pytest.raises(OperationalError):
                built.connect()
        finally:
            built.dispose()

    # One attempt per engine, each bounded by the configured value even though
    # the writer DSN carries connect_timeout=300 of its own.
    assert [kwargs.get("connect_timeout") for kwargs in recorded] == [4, 4]
