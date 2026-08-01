from fastapi.testclient import TestClient

from tests.metrics import assert_metrics_contract


def test_guard_app_startup(guard_client: TestClient):
    response = guard_client.get("/openapi.json")

    assert response.status_code == 200
    assert_metrics_contract(guard_client, "guard")
