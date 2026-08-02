from fastapi.testclient import TestClient

METRICS_API_KEY = "test-metrics-api-key"


def assert_metrics_contract(client: TestClient, namespace: str) -> None:
    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    assert "/metrics" not in openapi_response.json()["paths"]

    missing_credentials = client.get("/metrics")
    assert missing_credentials.status_code == 401
    assert missing_credentials.headers["WWW-Authenticate"] == "Bearer"

    invalid_credentials = client.get(
        "/metrics",
        headers={"Authorization": "Bearer invalid-metrics-api-key"},
    )
    assert invalid_credentials.status_code == 401
    assert invalid_credentials.headers["WWW-Authenticate"] == "Bearer"
    assert invalid_credentials.json() == missing_credentials.json()

    query_credentials = client.get("/metrics", params={"secret": METRICS_API_KEY})
    assert query_credentials.status_code == 401

    response = client.get(
        "/metrics",
        headers={"Authorization": f"Bearer {METRICS_API_KEY}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert f'{namespace}_api_http_requests_total{{handler="/openapi.json",method="GET",status="2xx"}}' in response.text
    assert 'handler="/metrics"' not in response.text
    assert METRICS_API_KEY not in response.text
