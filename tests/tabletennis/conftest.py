from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def tabletennis_client() -> Iterator[TestClient]:
    from src.tabletennis import app as tabletennis_app

    with TestClient(tabletennis_app.app) as client:
        yield client
