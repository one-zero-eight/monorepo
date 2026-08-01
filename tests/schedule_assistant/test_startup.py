from fastapi.testclient import TestClient

from tests.metrics import assert_metrics_contract


def test_schedule_assistant_app_startup(schedule_assistant_client: TestClient):
    response = schedule_assistant_client.get("/openapi.json")
    assert response.status_code == 200
    assert_metrics_contract(schedule_assistant_client, "schedule_assistant")
