from fastapi.testclient import TestClient


def test_schedule_assistant_app_startup(schedule_assistant_client: TestClient):
    response = schedule_assistant_client.get("/openapi.json")
    assert response.status_code == 200
