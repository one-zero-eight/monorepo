import asyncio
import datetime as dtm
import fcntl
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import RSAKey
from sqlalchemy import text

from tests.schedule.constants import SAMPLE_EVENT_GROUP, SAMPLE_TAG

pytestmark = pytest.mark.xdist_group(name="schedule")

_SCHEDULE_DB_LOCK_PATH = Path(__file__).resolve().parent / ".schedule_test_db.lock"


@pytest.fixture(scope="session")
def schedule_client(request: pytest.FixtureRequest) -> Iterator[TestClient]:
    request.getfixturevalue("mock_inh_accounts_http")

    from src.schedule.config import settings
    from src.schedule.storages.sql import SQLAlchemyStorage

    async def prepare_schema() -> None:
        storage = SQLAlchemyStorage.from_url(settings.db_url.get_secret_value())
        await storage.create_all()
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

    lock_file = _SCHEDULE_DB_LOCK_PATH.open("w")
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
    try:
        client: TestClient = request.getfixturevalue("schedule_client")
        client.get("/openapi.json")
        assert client.portal is not None
        client.portal.call(_truncate_schedule_tables, client.app.state.sql_storage)
        _reset_predefined_storage()
        yield
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


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
