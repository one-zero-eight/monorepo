from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.room_booking.modules.bookings.schemas import Attendee, Booking
from tests.room_booking.datetime_helpers import dt_params, msk


def _awaited_room_ids(mock: AsyncMock) -> list[str]:
    assert mock.await_args is not None
    return mock.await_args.kwargs["room_ids"]


def _sample_booking(*, email: str = "test-user-1@innopolis.university") -> Booking:
    return Booking(
        room_id="3.1",
        title="Test booking",
        start=msk(2025, 6, 2, 10),
        end=msk(2025, 6, 2, 11),
        outlook_booking_id="booking-1",
        outlook_entry_id=None,
        attendees=[Attendee(email=email, status=None, assosiated_room_id=None)],
    )


@pytest.fixture
def mock_get_bookings(monkeypatch: pytest.MonkeyPatch):
    from src.room_booking.modules.bookings import routes as bookings_routes

    mock = AsyncMock(return_value=[])
    monkeypatch.setattr(bookings_routes.exchange_booking_repository, "get_bookings_for_certain_rooms", mock)
    return mock


def test_bookings_requires_auth(room_booking_client: TestClient):
    response = room_booking_client.get("/bookings/")
    assert response.status_code == 401


def test_bookings_date_validation(room_booking_client: TestClient, user_headers: dict[str, str]):
    response = room_booking_client.get(
        "/bookings/",
        params=dt_params(start=msk(2025, 6, 2, 12), end=msk(2025, 6, 2, 10)),
        headers=user_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Start must be before end"


def test_bookings_room_not_found(
    room_booking_client: TestClient, user_headers: dict[str, str], mock_get_bookings: AsyncMock
):
    response = room_booking_client.get(
        "/bookings/",
        params=dt_params(room_id="nonexistent-room", start=msk(2025, 6, 2, 10), end=msk(2025, 6, 2, 12)),
        headers=user_headers,
    )
    assert response.status_code == 404
    mock_get_bookings.assert_not_awaited()


def test_bookings_single_room_id(
    room_booking_client: TestClient,
    user_headers: dict[str, str],
    mock_get_bookings: AsyncMock,
):
    response = room_booking_client.get(
        "/bookings/",
        params=dt_params(room_id="3.1", start=msk(2025, 6, 2, 10), end=msk(2025, 6, 2, 12)),
        headers=user_headers,
    )
    assert response.status_code == 200
    mock_get_bookings.assert_awaited_once()
    assert _awaited_room_ids(mock_get_bookings) == ["3.1"]


def test_bookings_room_id_and_room_ids_merged(
    room_booking_client: TestClient,
    user_headers: dict[str, str],
    mock_get_bookings: AsyncMock,
):
    response = room_booking_client.get(
        "/bookings/",
        params=dt_params(room_id="3.1", room_ids=["3.2"], start=msk(2025, 6, 2, 10), end=msk(2025, 6, 2, 12)),
        headers=user_headers,
    )
    assert response.status_code == 200
    assert _awaited_room_ids(mock_get_bookings) == ["3.1", "3.2"]


def test_bookings_all_rooms_when_no_filter(
    room_booking_client: TestClient,
    user_headers: dict[str, str],
    mock_get_bookings: AsyncMock,
):
    response = room_booking_client.get(
        "/bookings/",
        params=dt_params(start=msk(2025, 6, 2, 10), end=msk(2025, 6, 2, 12)),
        headers=user_headers,
    )
    assert response.status_code == 200
    room_ids = _awaited_room_ids(mock_get_bookings)
    assert "3.1" in room_ids
    assert "101" not in room_ids


def test_bookings_service_auth_skips_related_to_me(
    room_booking_client: TestClient,
    api_key_headers: dict[str, str],
    mock_get_bookings: AsyncMock,
):
    mock_get_bookings.return_value = [_sample_booking()]
    response = room_booking_client.get(
        "/bookings/",
        params=dt_params(room_id="3.1", start=msk(2025, 6, 2, 10), end=msk(2025, 6, 2, 12)),
        headers=api_key_headers,
    )
    assert response.status_code == 200
    assert response.json()[0]["related_to_me"] is None


def test_bookings_user_sets_related_to_me(
    room_booking_client: TestClient,
    user_headers: dict[str, str],
    mock_get_bookings: AsyncMock,
):
    mock_get_bookings.return_value = [_sample_booking()]
    response = room_booking_client.get(
        "/bookings/",
        params=dt_params(room_id="3.1", start=msk(2025, 6, 2, 10), end=msk(2025, 6, 2, 12)),
        headers=user_headers,
    )
    assert response.status_code == 200
    assert response.json()[0]["related_to_me"] is True


def _calendar_item_with_user(email: str) -> MagicMock:
    attendee = MagicMock()
    attendee.mailbox.email_address = email
    attendee.response_type = "Accept"
    item = MagicMock()
    item.required_attendees = [attendee]
    item.resources = []
    return item


@pytest.fixture
def mock_cancel_extra_by_booking_id(monkeypatch: pytest.MonkeyPatch):
    from src.room_booking.modules.bookings import routes as bookings_routes

    calendar_item = _calendar_item_with_user("test-user-1@innopolis.university")
    get_booking = AsyncMock(return_value=calendar_item)
    cancel_booking = AsyncMock(return_value=True)
    monkeypatch.setattr(bookings_routes.exchange_booking_repository, "get_booking", get_booking)
    monkeypatch.setattr(bookings_routes.exchange_booking_repository, "cancel_booking", cancel_booking)
    return get_booking, cancel_booking


@pytest.fixture
def mock_cancel_extra_by_bmp_slot(monkeypatch: pytest.MonkeyPatch):
    from src.room_booking.modules.bookings import routes as bookings_routes

    cancel_slot = AsyncMock(return_value=True)
    monkeypatch.setattr(bookings_routes.bmp_repository, "cancel_auto_booking_by_slot", cancel_slot)
    return cancel_slot


def test_cancel_extra_by_outlook_booking_id(
    room_booking_client: TestClient,
    user_headers: dict[str, str],
    mock_cancel_extra_by_booking_id: tuple[AsyncMock, AsyncMock],
):
    get_booking, cancel_booking = mock_cancel_extra_by_booking_id
    response = room_booking_client.post(
        "/bookings/cancel-extra",
        headers=user_headers,
        json={
            "room_id": "3.1",
            "start": msk(2025, 6, 2, 10).isoformat(),
            "end": msk(2025, 6, 2, 11).isoformat(),
            "title": "Test booking",
            "outlook_booking_id": "booking-1",
        },
    )
    assert response.status_code == 200
    get_booking.assert_awaited_once_with("booking-1")
    cancel_booking.assert_awaited_once()


def test_cancel_extra_by_bmp_slot(
    room_booking_client: TestClient,
    user_headers: dict[str, str],
    mock_cancel_extra_by_bmp_slot: AsyncMock,
):
    response = room_booking_client.post(
        "/bookings/cancel-extra",
        headers=user_headers,
        json={
            "room_id": "3.1",
            "start": msk(2025, 6, 2, 10).isoformat(),
            "end": msk(2025, 6, 2, 11).isoformat(),
            "title": "Auto booking",
        },
    )
    assert response.status_code == 200
    mock_cancel_extra_by_bmp_slot.assert_awaited_once()
