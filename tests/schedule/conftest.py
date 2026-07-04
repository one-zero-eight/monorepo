import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


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
