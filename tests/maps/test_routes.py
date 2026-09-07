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


def test_scenes_endpoint_returns_geo_reference(maps_client: TestClient):
    response = maps_client.get("/scenes/")
    assert response.status_code == 200
    scenes = {scene["scene_id"]: scene for scene in response.json()}

    university_floor = scenes["university-floor-1"]
    geo_reference = university_floor["geo_reference"]
    assert geo_reference is not None
    assert geo_reference["accuracy_threshold_m"] == 150
    control_points = geo_reference["control_points"]
    assert len(control_points) == 6
    for point in control_points:
        assert set(point) == {"label", "lat", "lon", "x", "y"}

    # Every university floor shares the same calibration.
    for scene_id in (
        "university-floor-0",
        "university-floor-2",
        "university-floor-3",
        "university-floor-4",
        "university-floor-5",
    ):
        assert scenes[scene_id]["geo_reference"] == geo_reference

    # Scenes without calibration have no location dot.
    assert scenes["sport-complex"]["geo_reference"] is None
    assert scenes["campus"]["geo_reference"] is None


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


def test_pdf_endpoint_returns_pdf(maps_client: TestClient):
    response = maps_client.get("/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 0
