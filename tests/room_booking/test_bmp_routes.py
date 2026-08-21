import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.room_booking.modules.bmp.repository import BmpBatchItemResult
from src.room_booking.modules.bookings.schemas import Booking
from tests.room_booking.datetime_helpers import dt_params, msk


def _ndjson_events(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


@pytest.fixture
def mock_bmp_create_booking(monkeypatch: pytest.MonkeyPatch):
    from src.room_booking.modules.bmp import routes as bmp_routes

    booking = Booking(
        room_id="3.1",
        title="Auto",
        start=msk(2025, 6, 2, 10),
        end=msk(2025, 6, 2, 11),
        outlook_booking_id="auto-1",
        outlook_entry_id=None,
        attendees=None,
    )
    mock = AsyncMock(return_value=booking)
    monkeypatch.setattr(bmp_routes.bmp_repository, "create_booking", mock)
    return mock


def test_bmp_auto_bookings_requires_api_key(room_booking_client: TestClient):
    response = room_booking_client.get("/bmp/auto-bookings/")
    assert response.status_code == 401


def test_bmp_auto_bookings_date_validation(room_booking_client: TestClient, api_key_headers: dict[str, str]):
    response = room_booking_client.get(
        "/bmp/auto-bookings/",
        params=dt_params(start=msk(2025, 6, 2, 12), end=msk(2025, 6, 2, 10)),
        headers=api_key_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Start must be before end"


def test_bmp_batch_invalid_dates(room_booking_client: TestClient, api_key_headers: dict[str, str]):
    response = room_booking_client.post(
        "/bmp/auto-bookings/batch",
        headers=api_key_headers,
        json={
            "bookings": [
                {
                    "room_id": "3.1",
                    "title": "Bad",
                    "start": msk(2025, 6, 2, 12).isoformat(),
                    "end": msk(2025, 6, 2, 10).isoformat(),
                    "participant_emails": None,
                }
            ]
        },
    )
    assert response.status_code == 200
    events = _ndjson_events(response)
    assert events[0] == {"event": "started", "total": 1}
    assert events[1]["event"] == "item"
    assert events[1]["index"] == "0"
    assert events[1]["status"] == "error"
    assert events[1]["title"] == "Bad"
    assert events[1]["error"] == "Start must be before end"
    assert events[-1] == {"event": "done"}


def test_bmp_batch_unknown_room(room_booking_client: TestClient, api_key_headers: dict[str, str]):
    response = room_booking_client.post(
        "/bmp/auto-bookings/batch",
        headers=api_key_headers,
        json={
            "bookings": [
                {
                    "room_id": "nonexistent-room",
                    "title": "Missing room",
                    "start": msk(2025, 6, 2, 10).isoformat(),
                    "end": msk(2025, 6, 2, 11).isoformat(),
                    "participant_emails": None,
                }
            ]
        },
    )
    assert response.status_code == 200
    events = _ndjson_events(response)
    item = next(event for event in events if event["event"] == "item")
    assert item["status"] == "error"
    assert item["error"] == "Room not found"
    assert item["title"] == "Missing room"


def test_bmp_create_auto_booking(
    room_booking_client: TestClient,
    api_key_headers: dict[str, str],
    mock_bmp_create_booking: AsyncMock,
):
    response = room_booking_client.post(
        "/bmp/auto-bookings/",
        headers=api_key_headers,
        json={
            "room_id": "3.1",
            "title": "Auto",
            "start": msk(2025, 6, 2, 10).isoformat(),
            "end": msk(2025, 6, 2, 11).isoformat(),
            "participant_emails": None,
        },
    )
    assert response.status_code == 200
    assert response.json()["outlook_booking_id"] == "auto-1"
    mock_bmp_create_booking.assert_awaited_once()


def test_bmp_batch_valid_entry_streams_sent_then_item(
    room_booking_client: TestClient,
    api_key_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    from src.room_booking.modules.bmp import routes as bmp_routes

    booking = Booking(
        room_id="3.1",
        title="Auto",
        start=msk(2025, 6, 2, 10),
        end=msk(2025, 6, 2, 11),
        outlook_booking_id="auto-1",
        outlook_entry_id=None,
        attendees=None,
    )

    async def fake_iter(_entries):
        yield (None, None, [0])
        yield (0, BmpBatchItemResult(status="ok", booking=booking, error=None), None)

    monkeypatch.setattr(bmp_routes.bmp_repository, "iter_create_bookings_batch", fake_iter)

    response = room_booking_client.post(
        "/bmp/auto-bookings/batch",
        headers=api_key_headers,
        json={
            "bookings": [
                {
                    "room_id": "3.1",
                    "title": "Auto",
                    "start": msk(2025, 6, 2, 10).isoformat(),
                    "end": msk(2025, 6, 2, 11).isoformat(),
                    "participant_emails": None,
                }
            ]
        },
    )
    assert response.status_code == 200
    events = _ndjson_events(response)
    assert events[0] == {"event": "started", "total": 1}
    assert events[1] == {"event": "sent", "indexes": ["0"]}
    assert events[2]["event"] == "item"
    assert events[2]["index"] == "0"
    assert events[2]["status"] == "ok"
    assert events[2]["title"] == "Auto"
    assert events[3] == {"event": "done"}


def test_bmp_batch_emits_ping_while_create_is_idle(
    room_booking_client: TestClient,
    api_key_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    from src.room_booking.modules.bmp import routes as bmp_routes

    booking = Booking(
        room_id="3.1",
        title="Auto",
        start=msk(2025, 6, 2, 10),
        end=msk(2025, 6, 2, 11),
        outlook_booking_id="auto-1",
        outlook_entry_id=None,
        attendees=None,
    )

    async def fake_iter(_entries):
        await asyncio.sleep(0.05)
        yield (None, None, [0])
        yield (0, BmpBatchItemResult(status="ok", booking=booking, error=None), None)

    monkeypatch.setattr(bmp_routes, "STREAM_PING_INTERVAL_S", 0.02)
    monkeypatch.setattr(bmp_routes.bmp_repository, "iter_create_bookings_batch", fake_iter)

    response = room_booking_client.post(
        "/bmp/auto-bookings/batch",
        headers=api_key_headers,
        json={
            "bookings": [
                {
                    "room_id": "3.1",
                    "title": "Auto",
                    "start": msk(2025, 6, 2, 10).isoformat(),
                    "end": msk(2025, 6, 2, 11).isoformat(),
                    "participant_emails": None,
                }
            ]
        },
    )
    assert response.status_code == 200
    events = _ndjson_events(response)
    kinds = [event["event"] for event in events]
    assert kinds[0] == "started"
    assert "ping" in kinds
    assert kinds[-1] == "done"
    assert "sent" in kinds
    assert "item" in kinds


def test_bmp_batch_creates_in_chunks(
    room_booking_client: TestClient,
    api_key_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    from src.room_booking.modules.bmp import repository as bmp_repository_module
    from src.room_booking.modules.bmp import routes as bmp_routes

    booking = Booking(
        room_id="3.1",
        title="Auto",
        start=msk(2025, 6, 2, 10),
        end=msk(2025, 6, 2, 11),
        outlook_booking_id="auto-1",
        outlook_entry_id=None,
        attendees=None,
    )
    chunk_sizes: list[int] = []

    async def fake_chunk(entries):
        chunk_sizes.append(len(entries))
        yield (None, None, list(range(len(entries))))
        for index in range(len(entries)):
            yield (index, BmpBatchItemResult(status="ok", booking=booking, error=None), None)

    monkeypatch.setattr(bmp_repository_module, "BMP_CREATE_CHUNK_SIZE", 1)
    monkeypatch.setattr(bmp_routes.bmp_repository, "_iter_create_bookings_chunk", fake_chunk)

    response = room_booking_client.post(
        "/bmp/auto-bookings/batch",
        headers=api_key_headers,
        json={
            "bookings": [
                {
                    "room_id": "3.1",
                    "title": "First",
                    "start": msk(2025, 6, 2, 10).isoformat(),
                    "end": msk(2025, 6, 2, 11).isoformat(),
                    "participant_emails": None,
                },
                {
                    "room_id": "3.1",
                    "title": "Second",
                    "start": msk(2025, 6, 2, 12).isoformat(),
                    "end": msk(2025, 6, 2, 13).isoformat(),
                    "participant_emails": None,
                },
            ]
        },
    )
    assert response.status_code == 200
    assert chunk_sizes == [1, 1]
    events = _ndjson_events(response)
    sent_indexes = [event["indexes"] for event in events if event["event"] == "sent"]
    item_indexes = [event["index"] for event in events if event["event"] == "item"]
    assert sent_indexes == [["0"], ["1"]]
    assert item_indexes == ["0", "1"]


def _calendar_item_with_user(email: str):
    from unittest.mock import MagicMock

    attendee = MagicMock()
    attendee.mailbox.email_address = email
    attendee.response_type = "Accept"
    item = MagicMock()
    item.required_attendees = [attendee]
    item.resources = []
    return item


@pytest.fixture
def mock_cancel_extra_by_booking_id(monkeypatch: pytest.MonkeyPatch):
    from src.room_booking.modules.bmp import routes as bmp_routes

    calendar_item = _calendar_item_with_user("test-user-1@innopolis.university")
    get_booking = AsyncMock(return_value=calendar_item)
    cancel_booking = AsyncMock(return_value=True)
    monkeypatch.setattr(bmp_routes.exchange_booking_repository, "get_booking", get_booking)
    monkeypatch.setattr(bmp_routes.exchange_booking_repository, "cancel_booking", cancel_booking)
    return get_booking, cancel_booking


@pytest.fixture
def mock_cancel_extra_by_bmp_slot(monkeypatch: pytest.MonkeyPatch):
    from src.room_booking.modules.bmp import routes as bmp_routes

    cancel_slot = AsyncMock(return_value=True)
    monkeypatch.setattr(bmp_routes.bmp_repository, "cancel_auto_booking_by_slot", cancel_slot)
    return cancel_slot


def test_cancel_extra_auto_booking_by_outlook_id(
    room_booking_client: TestClient,
    api_key_headers: dict[str, str],
    mock_cancel_extra_by_booking_id: tuple[AsyncMock, AsyncMock],
):
    get_booking, cancel_booking = mock_cancel_extra_by_booking_id
    response = room_booking_client.post(
        "/bmp/auto-bookings/cancel-extra",
        headers=api_key_headers,
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


def test_cancel_extra_auto_booking_requires_api_key(
    room_booking_client: TestClient,
    user_headers: dict[str, str],
    mock_cancel_extra_by_bmp_slot: AsyncMock,
):
    response = room_booking_client.post(
        "/bmp/auto-bookings/cancel-extra",
        headers=user_headers,
        json={
            "room_id": "3.1",
            "start": msk(2025, 6, 2, 10).isoformat(),
            "end": msk(2025, 6, 2, 11).isoformat(),
            "title": "Auto booking",
        },
    )
    assert response.status_code == 401
    mock_cancel_extra_by_bmp_slot.assert_not_awaited()


def test_cancel_extra_auto_booking_by_slot(
    room_booking_client: TestClient,
    api_key_headers: dict[str, str],
    mock_cancel_extra_by_bmp_slot: AsyncMock,
):
    response = room_booking_client.post(
        "/bmp/auto-bookings/cancel-extra",
        headers=api_key_headers,
        json={
            "room_id": "3.1",
            "start": msk(2025, 6, 2, 10).isoformat(),
            "end": msk(2025, 6, 2, 11).isoformat(),
            "title": "Auto booking",
        },
    )
    assert response.status_code == 200
    mock_cancel_extra_by_bmp_slot.assert_awaited_once()
