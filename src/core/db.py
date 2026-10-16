from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings


# Applies when config/settings.yaml cannot provide a value (a direct
# ``Settings()`` caller, or a test). The bound must never be absent: libpq's
# own default is to wait forever.
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10

_engine = None
_session_factory = None
_agent_engine = None
_agent_session_factory = None


def connect_timeout_seconds() -> int:
    """The service-owned bound on every connection attempt, in seconds.

    Both engines and the checkpointer pool carry this in their connect
    arguments, so a DSN that has no ``connect_timeout``, or a different one,
    cannot change the bound the service enforces: SQLAlchemy merges
    ``connect_args`` over the URL's query parameters, and psycopg merges keyword
    arguments over the connection string (#642).
    """
    database_config = settings.config_yaml.get("database")
    if isinstance(database_config, dict):
        value = database_config.get("connect_timeout_seconds")
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    return DEFAULT_CONNECT_TIMEOUT_SECONDS


def _connect_args() -> dict[str, int]:
    return {"connect_timeout": connect_timeout_seconds()}


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            connect_args=_connect_args(),
        )
    return _engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=_get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _session_factory


def _get_agent_engine():
    global _agent_engine
    if _agent_engine is None:
        _agent_engine = create_engine(
            settings.AGENT_DATABASE_URL,
            pool_pre_ping=True,
            connect_args=_connect_args(),
        )
    return _agent_engine


def _get_agent_session_factory():
    global _agent_session_factory
    if _agent_session_factory is None:
        _agent_session_factory = sessionmaker(
            bind=_get_agent_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _agent_session_factory


class _EngineProxy:
    def __getattr__(self, name):
        return getattr(_get_engine(), name)


class _SessionFactoryProxy:
    def __call__(self, *args, **kwargs):
        return _get_session_factory()(*args, **kwargs)

    @property
    def kw(self):
        return _get_session_factory().kw


class _AgentSessionFactoryProxy:
    def __call__(self, *args, **kwargs):
        return _get_agent_session_factory()(*args, **kwargs)

    @property
    def kw(self):
        return _get_agent_session_factory().kw


engine = _EngineProxy()
session_factory = _SessionFactoryProxy()
agent_session_factory = _AgentSessionFactoryProxy()
