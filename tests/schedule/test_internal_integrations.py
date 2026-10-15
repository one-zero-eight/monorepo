import datetime as dtm
from zlib import crc32

import httpx
import icalendar
import pytest
import respx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr


@pytest.mark.parametrize("status", [401, 403, 503])
def test_assistant_errors_are_bad_gateway(schedule_client: TestClient, monkeypatch: pytest.MonkeyPatch, status: int):
    from src.schedule.config import settings
    from src.schedule.config_schema import ScheduleAssistantIntegrationSettings

    monkeypatch.setattr(
        settings,
        "schedule_assistant",
        ScheduleAssistantIntegrationSettings(api_url="https://assistant-errors.test", api_key=SecretStr("key")),
    )
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://assistant-errors.test/integration/event-groups").respond(status, text="unavailable")
        response = schedule_client.get("/event-groups/")
    assert response.status_code == 502
    assert response.json()["detail"] == f"Schedule Assistant request failed with status {status}"


def test_assistant_transport_failure_is_bad_gateway(schedule_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from src.schedule.config import settings
    from src.schedule.config_schema import ScheduleAssistantIntegrationSettings

    monkeypatch.setattr(
        settings,
        "schedule_assistant",
        ScheduleAssistantIntegrationSettings(api_url="https://assistant-timeout.test", api_key=SecretStr("key")),
    )
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://assistant-timeout.test/integration/event-groups").mock(
            side_effect=httpx.ConnectTimeout("timeout")
        )
        response = schedule_client.get("/event-groups/")
    assert response.status_code == 502
    assert response.json()["detail"] == "Schedule Assistant request failed"


def test_room_booking_calendar_uses_current_contract(
    schedule_client: TestClient, user_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    from src.schedule.config import settings
    from src.schedule.config_schema import RoomBookingIntegrationSettings

    monkeypatch.setattr(
        settings,
        "room_booking",
        RoomBookingIntegrationSettings(api_url="https://booking.test/prefix/v0", api_key=SecretStr("room-key")),
    )
    booking = {
        "id": "booking-record",
        "room_id": "303",
        "title": "Комната",
        "start": "2026-10-15T10:00:00",
        "end": "2026-10-15T11:00:00Z",
        "outlook_booking_id": "outlook-id",
        "outlook_entry_id": "entry-id",
        "attendees": [],
    }
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get("https://booking.test/prefix/v0/user/test-user-1/bookings").respond(200, json=[booking])
        response = schedule_client.get("/users/me/room-bookings.ics", headers=user_headers)
    assert response.status_code == 200
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer room-key"
    start = dtm.datetime.fromisoformat(request.url.params["start"])
    end = dtm.datetime.fromisoformat(request.url.params["end"])
    assert start.timetz() == dtm.time(0, tzinfo=dtm.UTC)
    assert dtm.timedelta(days=14) <= end - start < dtm.timedelta(days=15)
    event = icalendar.Calendar.from_ical(response.content).walk("VEVENT")[0]
    assert str(event["uid"]) == f"room-booking-{crc32(b'outlook-id'):x}@innohassle.ru"
    assert str(event["summary"]) == "Комната"
    assert str(event["location"]) == "303"
    assert str(event["x-room-booking-id"]) == "outlook-id"
    assert event.decoded("dtstart") == dtm.datetime(2026, 10, 15, 10, tzinfo=dtm.UTC)


def test_room_booking_not_configured(schedule_client: TestClient, user_headers: dict[str, str]):
    response = schedule_client.get("/users/me/room-bookings.ics", headers=user_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Room booking service is not configured"


def test_events_rejects_unpublished_export(schedule_client: TestClient):
    response = schedule_client.get("/events.ics", params={"only_published": False})
    assert response.status_code == 400
    assert response.json()["detail"] == "Events only supports published calendar exports"


def test_room_booking_requires_linked_account(schedule_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from src.schedule.config import settings
    from src.schedule.config_schema import RoomBookingIntegrationSettings
    from src.schedule.modules.ics.utils import get_personal_room_bookings
    from src.schedule.modules.users.schemas import ViewUser

    monkeypatch.setattr(
        settings,
        "room_booking",
        RoomBookingIntegrationSettings(api_url="https://booking.test", api_key=SecretStr("key")),
    )
    user = ViewUser(
        id=1,
        email="unlinked@example.test",
        music_room_hidden=False,
        sports_hidden=False,
        moodle_hidden=False,
        events_hidden=False,
        room_bookings_hidden=False,
    )
    assert schedule_client.portal is not None
    with pytest.raises(HTTPException) as error:
        schedule_client.portal.call(get_personal_room_bookings, user)
    assert error.value.status_code == 404
    assert error.value.detail == "User has no innohassle account linked"


def test_generated_wrappers_observe_current_settings(schedule_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from src.schedule.config import settings
    from src.schedule.config_schema import EventsSettings, ScheduleAssistantIntegrationSettings

    calendar = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n"
    with respx.mock(assert_all_called=True) as mock:
        for index in range(2):
            url = f"https://integration-{index}.test/prefix"
            key = f"key-{index}"
            monkeypatch.setattr(settings, "events", EventsSettings(api_url=url, api_key=SecretStr(key)))
            monkeypatch.setattr(
                settings,
                "schedule_assistant",
                ScheduleAssistantIntegrationSettings(api_url=url, api_key=SecretStr(key)),
            )
            events = mock.get(f"{url}/events.ics").respond(200, text=calendar)
            assistant = mock.get(f"{url}/integration/event-groups/group/schedule.ics").respond(200, text=calendar)
            assert schedule_client.get("/events.ics").content == calendar.encode()
            assert (
                schedule_client.get("/group.ics", params={"user_id": 1, "export_type": "default"}).content
                == calendar.encode()
            )
            assert events.calls[0].request.headers["authorization"] == f"Bearer {key}"
            assert assistant.calls[0].request.headers["authorization"] == f"Bearer {key}"


def test_integration_clients_close_and_reopen(schedule_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from src.schedule.config import settings
    from src.schedule.config_schema import RoomBookingIntegrationSettings, ScheduleAssistantIntegrationSettings
    from src.schedule.modules.ics.utils import InternalIntegrationClients
    from src.schedule.modules.schedule_assistant.client import ScheduleAssistantClient

    monkeypatch.setattr(
        settings,
        "room_booking",
        RoomBookingIntegrationSettings(api_url="https://lifecycle.test", api_key=SecretStr("key")),
    )
    monkeypatch.setattr(
        settings,
        "schedule_assistant",
        ScheduleAssistantIntegrationSettings(api_url="https://lifecycle.test", api_key=SecretStr("key")),
    )

    async def exercise() -> None:
        internal = InternalIntegrationClients()
        assistant = ScheduleAssistantClient()
        with respx.mock(assert_all_called=True) as mock:
            mock.get("https://lifecycle.test/user/user/bookings").respond(200, json=[])
            mock.get("https://lifecycle.test/integration/users/user%40example.test/predefined").respond(
                200, json={"event_groups": ["group"]}
            )
            for _ in range(2):
                assert await internal.room_booking().bookings_get_user_bookings("user") == []
                assert await assistant.get_user_predefined("user@example.test") == ["group"]
                await internal.aclose()
                await assistant.aclose()
        await internal.aclose()
        await assistant.aclose()

    assert schedule_client.portal is not None
    schedule_client.portal.call(exercise)
