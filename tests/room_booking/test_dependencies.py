from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_list_auto_bookings(monkeypatch: pytest.MonkeyPatch):
    from src.room_booking.modules.bmp import routes as bmp_routes

    mock = AsyncMock(return_value=[])
    monkeypatch.setattr(bmp_routes.bmp_repository, "list_auto_bookings", mock)
    return mock


def test_rooms_requires_auth(room_booking_client: TestClient):
    response = room_booking_client.get("/rooms/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Credentials not provided"


def test_rooms_wrong_bearer(room_booking_client: TestClient):
    response = room_booking_client.get("/rooms/", headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Unable to verify credentials"


def test_rooms_with_jwt(room_booking_client: TestClient, user_headers: dict[str, str]):
    response = room_booking_client.get("/rooms/", headers=user_headers)
    assert response.status_code == 200
    room_ids = {room["id"] for room in response.json()}
    assert "3.1" in room_ids
    assert "101" not in room_ids


def test_rooms_with_api_key(room_booking_client: TestClient, api_key_headers: dict[str, str]):
    response = room_booking_client.get("/rooms/", headers=api_key_headers)
    assert response.status_code == 200


def test_bmp_requires_api_key(room_booking_client: TestClient):
    response = room_booking_client.get("/bmp/auto-bookings/")
    assert response.status_code == 401


def test_bmp_rejects_jwt(room_booking_client: TestClient, user_headers: dict[str, str]):
    response = room_booking_client.get("/bmp/auto-bookings/", headers=user_headers)
    assert response.status_code == 401


def test_bmp_accepts_api_key(
    room_booking_client: TestClient,
    api_key_headers: dict[str, str],
    mock_list_auto_bookings: AsyncMock,
):
    response = room_booking_client.get("/bmp/auto-bookings/", headers=api_key_headers)
    assert response.status_code == 200
    assert response.json() == []
    mock_list_auto_bookings.assert_awaited_once()
