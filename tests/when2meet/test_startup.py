from fastapi.testclient import TestClient

from tests.metrics import assert_metrics_contract


def test_when2meet_app_startup(when2meet_client: TestClient):
    response = when2meet_client.get("/openapi.json")
    assert response.status_code == 200
    assert_metrics_contract(when2meet_client, "when2meet")
