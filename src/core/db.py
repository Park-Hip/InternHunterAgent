from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings


_engine = None
_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
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


class _EngineProxy:
    def __getattr__(self, name):
        return getattr(_get_engine(), name)


class _SessionFactoryProxy:
    def __call__(self, *args, **kwargs):
        return _get_session_factory()(*args, **kwargs)

    @property
    def kw(self):
        return _get_session_factory().kw


engine = _EngineProxy()
session_factory = _SessionFactoryProxy()
