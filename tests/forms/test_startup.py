from fastapi.testclient import TestClient

from tests.metrics import assert_metrics_contract


def test_forms_app_startup(forms_client: TestClient):
    response = forms_client.get("/openapi.json")
    assert response.status_code == 200
    assert_metrics_contract(forms_client, "forms")
