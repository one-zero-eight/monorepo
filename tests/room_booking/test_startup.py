from fastapi.testclient import TestClient

from tests.metrics import assert_metrics_contract


def test_room_booking_app_startup(room_booking_client: TestClient):
    response = room_booking_client.get("/openapi.json")
    assert response.status_code == 200
    assert_metrics_contract(room_booking_client, "room_booking")
