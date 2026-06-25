from fastapi.testclient import TestClient


def test_room_booking_app_startup(room_booking_client: TestClient):
    response = room_booking_client.get("/openapi.json")
    assert response.status_code == 200
