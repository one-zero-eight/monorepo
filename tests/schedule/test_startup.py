from fastapi.testclient import TestClient


def test_schedule_app_startup(schedule_client: TestClient):
    response = schedule_client.get("/openapi.json")
    assert response.status_code == 200
