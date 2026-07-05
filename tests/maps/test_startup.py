from fastapi.testclient import TestClient


def test_maps_app_startup(maps_client: TestClient):
    response = maps_client.get("/openapi.json")
    assert response.status_code == 200
