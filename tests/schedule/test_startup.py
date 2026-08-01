from fastapi.testclient import TestClient

from tests.metrics import assert_metrics_contract


def test_schedule_app_startup(schedule_client: TestClient):
    response = schedule_client.get("/openapi.json")
    assert response.status_code == 200
    assert_metrics_contract(schedule_client, "schedule")
