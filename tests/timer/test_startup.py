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
