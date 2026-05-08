from fastapi.testclient import TestClient


def test_clubs_app_startup():
    from src.clubs import app as clubs_app

    with TestClient(clubs_app.app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
