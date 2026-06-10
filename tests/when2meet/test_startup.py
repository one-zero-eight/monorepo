from fastapi.testclient import TestClient


def test_when2meet_app_startup(when2meet_client: TestClient):
    response = when2meet_client.get("/openapi.json")
    assert response.status_code == 200


def test_when2meet_health(when2meet_client: TestClient):
    response = when2meet_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
