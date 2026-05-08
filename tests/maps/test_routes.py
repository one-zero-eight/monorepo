from fastapi.testclient import TestClient


def test_maps_startup_openapi(maps_client: TestClient):
    response = maps_client.get("/openapi.json")
    assert response.status_code == 200


def test_scenes_endpoint_returns_data(maps_client: TestClient):
    response = maps_client.get("/scenes/")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) > 0
    assert "scene_id" in payload[0]


def test_search_endpoint_validation(maps_client: TestClient):
    response = maps_client.get("/scenes/areas/search")
    assert response.status_code == 422


def test_search_endpoint_returns_results(maps_client: TestClient):
    response = maps_client.get("/scenes/areas/search", params={"query": "305"})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) > 0
    assert payload[0]["scene_id"] == "university-floor-3"
