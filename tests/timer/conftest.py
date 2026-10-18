import asyncio
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="session")
def timer_client(request: pytest.FixtureRequest) -> Iterator[TestClient]:
    request.getfixturevalue("mock_inh_accounts_http")

    from src.timer.config import settings

    configured_url = make_url(settings.db_url.get_secret_value())
    database_name = f"{configured_url.database}-{uuid4().hex}"
    database_url = configured_url.set(database=database_name)
    admin_engine = create_async_engine(
        configured_url.set(database="postgres"), poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    quoted_name = admin_engine.dialect.identifier_preparer.quote(database_name)

    async def create_database() -> None:
        async with admin_engine.connect() as connection:
            await connection.execute(text(f"CREATE DATABASE {quoted_name}"))

    async def drop_database() -> None:
        try:
            async with admin_engine.connect() as connection:
                await connection.execute(text(f"DROP DATABASE {quoted_name} WITH (FORCE)"))
        finally:
            await admin_engine.dispose()

    asyncio.run(create_database())
    try:
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(settings, "db_url", SecretStr(database_url.render_as_string(hide_password=False)))
            migration_config = Config(Path(__file__).parents[2] / "src/timer/alembic.ini")
            migration_config.attributes["sqlalchemy.url"] = database_url.render_as_string(hide_password=False)
            command.upgrade(migration_config, "head")
            from src.timer.app import app

            with TestClient(app) as client:
                yield client
    finally:
        asyncio.run(drop_database())


@pytest.fixture(autouse=True)
def clean_timer_db(request: pytest.FixtureRequest):
    if "timer_client" not in request.fixturenames:
        yield
        return

    client: TestClient = request.getfixturevalue("timer_client")
    assert client.portal is not None

    async def clear_tables() -> None:
        async with client.app.state.sql_storage.engine.begin() as connection:
            await connection.execute(text("DELETE FROM timers"))

    client.portal.call(clear_tables)
    yield
