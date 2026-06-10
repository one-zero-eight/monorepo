from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def when2meet_client() -> Iterator[TestClient]:
    from src.when2meet import app as when2meet_app

    with TestClient(when2meet_app.app) as client:
        yield client
