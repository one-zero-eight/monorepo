from fastapi.testclient import TestClient


def test_schedule_app_startup(schedule_client: TestClient):
    response = schedule_client.get("/openapi.json")
    assert response.status_code == 200


def test_schedule_metrics(schedule_client: TestClient):
    assert schedule_client.get("/openapi.json").status_code == 200

    response = schedule_client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'http_requests_total{handler="/openapi.json",method="GET",status="2xx"}' in response.text
    assert 'handler="/metrics"' not in response.text
