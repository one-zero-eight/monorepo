from fastapi.testclient import TestClient

from tests.metrics import assert_metrics_contract


def test_events_app_startup(events_client: TestClient):
    response = events_client.get("/openapi.json")

    assert response.status_code == 200
    assert_metrics_contract(events_client, "events")
