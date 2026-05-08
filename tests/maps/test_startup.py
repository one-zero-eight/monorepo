from fastapi.testclient import TestClient


def test_maps_app_startup():
    from src.maps import app as maps_app

    with TestClient(maps_app.app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
