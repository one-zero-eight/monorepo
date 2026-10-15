"""SQLAlchemy engine and session factory (no FastAPI Depends)."""

from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.schedule_assistant.config import settings


@lru_cache
def _cached_engine(url: str) -> Engine:
    return create_engine(url)


def get_engine(db_url: str | None = None) -> Engine:
    """Return a process-wide engine for the resolved URL (None and explicit URL share one pool)."""
    return _cached_engine(db_url or settings.db_url.get_secret_value())


def clear_engine_cache() -> None:
    _cached_engine.cache_clear()


def get_session_factory(db_url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(db_url), autoflush=False, autocommit=False)


@contextmanager
def open_session(db_url: str | None = None) -> Generator[Session]:
    """Open a session outside HTTP (tests, scripts, background tasks). Caller commits."""
    session = get_session_factory(db_url)()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
