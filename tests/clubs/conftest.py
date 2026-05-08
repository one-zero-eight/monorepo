from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def clubs_client() -> Iterator[TestClient]:
    from src.clubs import app as clubs_app

    with TestClient(clubs_app.app) as client:
        yield client
