from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.schedule_assistant.config import settings
from src.schedule_assistant.db.base import Base


@lru_cache
def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or settings.database_url
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def _migrate_sqlite_schema(engine: Engine) -> None:
    if not str(engine.url).startswith("sqlite"):
        return
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(courses)"))}
        for column in ("short_name", "name_ru", "short_name_ru"):
            if column not in existing:
                conn.execute(text(f"ALTER TABLE courses ADD COLUMN {column} VARCHAR"))
        instructor_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(instructors)"))}
        if "slot_preferences" not in instructor_columns:
            conn.execute(text("ALTER TABLE instructors ADD COLUMN slot_preferences JSON NOT NULL DEFAULT '[]'"))


def init_db(database_url: str | None = None) -> None:
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    _migrate_sqlite_schema(engine)


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(database_url), autoflush=False, autocommit=False)


def get_db_session(database_url: str | None = None) -> Generator[Session]:
    session = get_session_factory(database_url)()
    try:
        yield session
    finally:
        session.close()
