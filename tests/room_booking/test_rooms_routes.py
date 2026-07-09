import datetime as dtm

from fastapi.testclient import TestClient

from src.room_booking.modules.bookings.tz_utils import msk_timezone
from tests.room_booking.datetime_helpers import dt_params, msk


def _future_booking_slot() -> tuple[dtm.datetime, dtm.datetime]:
    tomorrow = dtm.datetime.now(msk_timezone) + dtm.timedelta(days=1)
    start = tomorrow.replace(hour=20, minute=0, second=0, microsecond=0)
    end = start + dtm.timedelta(hours=1)
    return start, end


def test_rooms_requires_auth(room_booking_client: TestClient):
    response = room_booking_client.get("/rooms/")
    assert response.status_code == 401


def test_rooms_list_excludes_red_by_default(room_booking_client: TestClient, user_headers: dict[str, str]):
    response = room_booking_client.get("/rooms/", headers=user_headers)
    assert response.status_code == 200
    room_ids = {room["id"] for room in response.json()}
    assert "3.1" in room_ids
    assert "107" not in room_ids


def test_rooms_list_include_red(room_booking_client: TestClient, user_headers: dict[str, str]):
    response = room_booking_client.get("/rooms/", params={"include_red": "true"}, headers=user_headers)
    assert response.status_code == 200
    room_ids = {room["id"] for room in response.json()}
    assert "107" in room_ids


def test_room_can_book_allowed(room_booking_client: TestClient, user_headers: dict[str, str]):
    start, end = _future_booking_slot()
    response = room_booking_client.get(
        "/room/3.1/can-book",
        params=dt_params(start=start, end=end),
        headers=user_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["can_book"] is True
    assert not body["reason_why_cannot"]


def test_room_can_book_past_denied(room_booking_client: TestClient, user_headers: dict[str, str]):
    response = room_booking_client.get(
        "/room/3.1/can-book",
        params=dt_params(start=msk(2020, 1, 6, 10), end=msk(2020, 1, 6, 11)),
        headers=user_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["can_book"] is False
    assert "past" in body["reason_why_cannot"]


def test_room_can_book_not_found(room_booking_client: TestClient, user_headers: dict[str, str]):
    start, end = _future_booking_slot()
    response = room_booking_client.get(
        "/room/nonexistent/can-book",
        params=dt_params(start=start, end=end),
        headers=user_headers,
    )
    assert response.status_code == 404


def test_all_access_lists_forbidden_for_regular_user(room_booking_client: TestClient, user_headers: dict[str, str]):
    response = room_booking_client.get("/rooms/all-access-lists", headers=user_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "User is not an admin"


def test_all_access_lists_allowed_for_admin(room_booking_client: TestClient, superadmin_headers: dict[str, str]):
    response = room_booking_client.get("/rooms/all-access-lists", headers=superadmin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), dict)
