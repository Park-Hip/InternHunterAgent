from src.core.db import engine, session_factory


def test_db_exports_engine_and_session_factory() -> None:
    assert engine is not None
    assert session_factory is not None
    assert session_factory.kw["bind"] is engine


def test_engine_does_not_connect_on_import() -> None:
    # Importing the module should not require a live Postgres instance.
    assert engine.url.render_as_string(hide_password=False).startswith("postgresql+psycopg://")
