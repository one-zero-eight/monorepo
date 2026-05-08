from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def maps_client() -> Iterator[TestClient]:
    from src.maps import app as maps_app

    with TestClient(maps_app.app) as client:
        yield client
