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
