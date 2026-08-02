from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.schedule_assistant.config import settings


@lru_cache
def get_engine(db_url: str | None = None) -> Engine:
    url = db_url or settings.db_url.get_secret_value()
    return create_engine(url)


def get_session_factory(db_url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(db_url), autoflush=False, autocommit=False)


def get_db_session(db_url: str | None = None) -> Generator[Session]:
    session = get_session_factory(db_url)()
    try:
        yield session
    finally:
        session.close()
