from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def student_affairs_client() -> Iterator[TestClient]:
    from src.student_affairs import app as student_affairs_app

    with TestClient(student_affairs_app.app, raise_server_exceptions=False) as client:
        yield client
