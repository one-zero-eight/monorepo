import pytest
from fastapi.testclient import TestClient

from tests.metrics import assert_metrics_contract


def test_timer_app_startup(timer_client: TestClient):
    response = timer_client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "InNoHassle Timer API"
    assert_metrics_contract(timer_client, "timer")


def test_hello_requires_auth(timer_client: TestClient):
    assert timer_client.get("/hello").status_code == 401


def test_hello(timer_client: TestClient, user_headers: dict[str, str]):
    response = timer_client.get("/hello", headers=user_headers)
    assert response.status_code == 200
    assert response.json() == {"message": "hello, test-user-1@innopolis.university"}


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/timers/{timer_id}", "get"),
        ("/timers/{timer_id}", "put"),
        ("/timers/{timer_id}", "delete"),
        ("/timers/{timer_id}/invitations", "post"),
    ],
)
def test_timer_openapi_documents_not_found(timer_client: TestClient, path: str, method: str):
    response = timer_client.get("/openapi.json")
    assert response.status_code == 200
    responses = response.json()["paths"][path][method]["responses"]
    assert "404" in responses
    assert "403" not in responses
