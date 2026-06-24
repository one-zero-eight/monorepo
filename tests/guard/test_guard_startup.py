from fastapi.testclient import TestClient


def test_guard_app_startup(guard_client: TestClient):
    response = guard_client.get("/openapi.json")

    assert response.status_code == 200
