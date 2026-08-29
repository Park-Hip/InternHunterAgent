from src.core.db import agent_session_factory, engine, session_factory


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
    assert "+psycopg://internhunter:" in writer_url
    assert "+psycopg://internhunter_agent:" in agent_url
