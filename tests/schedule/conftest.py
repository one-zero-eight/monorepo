import asyncio
import datetime as dtm
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import RSAKey
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest_runtime_settings import SUITE_POSTGRES_NETLOC, schedule_test_database_name
from tests.schedule.constants import SAMPLE_EVENT_GROUP, SAMPLE_TAG


async def _ensure_postgres_database(admin_dsn: str, database_name: str) -> None:
    engine = create_async_engine(admin_dsn, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": database_name},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def schedule_client(request: pytest.FixtureRequest) -> Iterator[TestClient]:
    request.getfixturevalue("mock_inh_accounts_http")

    from src.schedule.config import settings
    from src.schedule.storages.sql import SQLAlchemyStorage

    async def prepare_schema() -> None:
        admin_dsn = f"postgresql+asyncpg://postgres:test@{SUITE_POSTGRES_NETLOC}/postgres"
        await _ensure_postgres_database(admin_dsn, schedule_test_database_name())
        settings.predefined_dir.mkdir(parents=True, exist_ok=True)
        storage = SQLAlchemyStorage.from_url(settings.db_url.get_secret_value())
        from src.schedule.storages.sql.models import Base

        async with storage.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await storage.close_connection()

    asyncio.run(prepare_schema())

    from src.schedule import app as schedule_app

    with TestClient(schedule_app.app) as client:
        yield client


@pytest.fixture
def schedule_portal(schedule_client: TestClient):
    assert schedule_client.portal is not None
    return schedule_client.portal


@pytest.fixture(scope="session")
def parser_headers(jwt_keypair: tuple[RSAKey, RSAKey]) -> dict[str, str]:
    private_key, _ = jwt_keypair
    now = int(dtm.datetime.now(dtm.UTC).timestamp())
    token = jwt.encode(
        {"alg": "RS256", "kid": "public"},
        {"sub": "parser", "iat": now, "exp": now + 3600},
        private_key,
    )
    token_str = token.decode() if isinstance(token, bytes) else token
    return {"Authorization": f"Bearer {token_str}"}


async def _truncate_schedule_tables(storage) -> None:
    from src.schedule.storages.sql.models import Base

    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    if not table_names:
        return
    async with storage.engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))


def _reset_predefined_storage() -> None:
    from src.schedule.modules.predefined.storage import JsonPredefinedUsers
    from src.schedule.modules.predefined.utils import setup_predefined_data_from_object

    setup_predefined_data_from_object(JsonPredefinedUsers())


@pytest.fixture(autouse=True)
def clean_schedule_db(request: pytest.FixtureRequest):
    if "schedule_client" not in request.fixturenames:
        yield
        return

    client: TestClient = request.getfixturevalue("schedule_client")
    client.get("/openapi.json")
    assert client.portal is not None
    client.portal.call(_truncate_schedule_tables, client.app.state.sql_storage)
    _reset_predefined_storage()
    yield


def create_tag(
    schedule_client: TestClient,
    parser_headers: dict[str, str],
    **overrides: Any,
) -> dict[str, Any]:
    tag = {**SAMPLE_TAG, **overrides}
    response = schedule_client.post(
        "/tags/batch-create-or-read",
        json={"tags": [tag]},
        headers=parser_headers,
    )
    assert response.status_code == 200
    return response.json()["tags"][0]


def create_event_group(
    schedule_client: TestClient,
    parser_headers: dict[str, str],
    **overrides: Any,
) -> dict[str, Any]:
    group = {**SAMPLE_EVENT_GROUP, **overrides}
    response = schedule_client.post("/event-groups/", json=group, headers=parser_headers)
    assert response.status_code == 201
    return response.json()
