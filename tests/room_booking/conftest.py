from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def room_booking_client(request: pytest.FixtureRequest) -> Iterator[TestClient]:
    request.getfixturevalue("mock_inh_accounts_http")
    from src.room_booking import app as room_booking_app

    with TestClient(room_booking_app.app, raise_server_exceptions=False) as client:
        yield client
