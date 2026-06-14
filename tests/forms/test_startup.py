from fastapi.testclient import TestClient


def test_forms_app_startup(forms_client: TestClient):
    response = forms_client.get("/openapi.json")
    assert response.status_code == 200
