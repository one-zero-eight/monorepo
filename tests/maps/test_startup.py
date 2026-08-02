from fastapi.testclient import TestClient

from tests.metrics import assert_metrics_contract


def test_maps_app_startup(maps_client: TestClient):
    response = maps_client.get("/openapi.json")
    assert response.status_code == 200
    assert_metrics_contract(maps_client, "maps")
