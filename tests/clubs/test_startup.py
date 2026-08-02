from fastapi.testclient import TestClient

from tests.metrics import assert_metrics_contract


def test_clubs_app_startup(clubs_client: TestClient):
    response = clubs_client.get("/openapi.json")

    assert response.status_code == 200
    assert_metrics_contract(clubs_client, "clubs")
