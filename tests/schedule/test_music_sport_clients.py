import datetime as dtm
from zlib import crc32

import icalendar
import pytest
import respx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.clients.sport_v3.exceptions import ApiError, ResponseValidationError
from src.inh_accounts_sdk import inh_accounts
from src.schedule.config import settings
from src.schedule.config_schema import MusicRoomSettings, SportSettings
from src.schedule.modules.ics.utils import get_music_room_ics, get_personal_sport_ics
from src.schedule.modules.users.schemas import ViewUser

MUSIC_URL = "https://music-room.test/v0"
SPORT_URL = "https://sport.test/api/v3"
ICAL = (
    "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:music@example.com\n"
    "DTSTART:20250101T100000Z\nDTEND:20250101T110000Z\nSUMMARY:Music room\nEND:VEVENT\nEND:VCALENDAR\n"
)


@pytest.fixture
def integrations(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "music_room", MusicRoomSettings(api_url=MUSIC_URL, api_key=SecretStr("music-key")))
    monkeypatch.setattr(settings, "sport", SportSettings(api_url=SPORT_URL))


def _personal_training(training_id: int, *, checked_in: bool = True, all_day: bool = False) -> dict:
    return {
        "training": {
            "id": training_id,
            "start": "2026-10-15T00:00:00+03:00" if all_day else "2026-10-15T17:00:00+03:00",
            "end": "2026-10-15T23:59:59+03:00" if all_day else "2026-10-15T19:00:00+03:00",
            "is_all_day": all_day,
            "training_location": None if all_day else {"id": 1, "name": "[SC] Big Hall"},
            "display_name": "Football",
            "sport_name": "Football",
            "group_name": None,
            "training_custom_name": None,
            "is_accredited": True,
            "is_club": False,
            "is_paid": False,
            "sport_id": 1,
            "group_id": 560,
            "checkins_count": 2,
            "max_checkins": 20,
        },
        "checked_in": checked_in,
        "can_check_in": False,
        "can_grade": False,
        "can_edit": False,
    }


def _user() -> ViewUser:
    return ViewUser(
        id=1,
        email="student@example.test",
        innohassle_id="student-1",
        music_room_hidden=False,
        sports_hidden=False,
        moodle_hidden=False,
        events_hidden=False,
        room_bookings_hidden=False,
    )


def test_music_room_public_generated_client(schedule_client: TestClient, integrations):
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(f"{MUSIC_URL}/music-room.ics").respond(200, text=ICAL)
        response = schedule_client.get("/music-room.ics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    event = icalendar.Calendar.from_ical(response.content).walk("VEVENT")[0]
    assert str(event["UID"]) == "music@example.com"
    assert route.calls[0].request.headers["accept"] == "text/calendar"


@pytest.mark.parametrize("keyed", [False, True])
def test_music_room_personal_generated_client(
    schedule_client: TestClient, user_headers: dict[str, str], integrations, keyed: bool
):
    user_id = schedule_client.get("/users/me", headers=user_headers).json()["id"]
    path = "/users/me/music-room.ics"
    params = {}
    if keyed:
        path = f"/users/{user_id}/music-room.ics"
        key = schedule_client.post(
            "/users/me/get-schedule-access-key", params={"resource_path": path}, headers=user_headers
        ).json()["access_key"]["access_key"]
        assert schedule_client.get(path, params={"access_key": "wrong"}).status_code == 403
        params = {"access_key": key}
    with respx.mock(assert_all_called=True) as mock:
        lookup = mock.get(f"{MUSIC_URL}/users/user_id", params={"email": "test-user-1@innopolis.university"}).respond(
            200, json=42
        )
        calendar = mock.get(f"{MUSIC_URL}/users/42/bookings.ics").respond(200, text=ICAL)
        response = schedule_client.get(path, params=params, headers={} if keyed else user_headers)
    assert response.status_code == 200
    assert b"music@example.com" in response.content
    for route in (lookup, calendar):
        assert route.calls[0].request.headers["authorization"] == "Bearer music-key"


def test_music_room_missing_user(schedule_client: TestClient, user_headers: dict[str, str], integrations):
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{MUSIC_URL}/users/user_id").respond(200, text="null", headers={"Content-Type": "application/json"})
        response = schedule_client.get("/users/me/music-room.ics", headers=user_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found in music room service"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,content,detail", [(503, "unavailable", "Error fetching calendar"), (200, "bad", "Invalid ICS format")]
)
async def test_music_room_calendar_errors(integrations, status: int, content: str, detail: str):
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{MUSIC_URL}/music-room.ics").respond(status, text=content)
        chunks = await get_music_room_ics()
        with pytest.raises(HTTPException, match=detail) as error:
            _ = [chunk async for chunk in chunks]
    assert error.value.status_code == 400


@pytest.mark.parametrize("keyed", [False, True])
def test_sport_v3_schedule_contract(
    schedule_client: TestClient, user_headers: dict[str, str], integrations, keyed: bool
):
    user_id = schedule_client.get("/users/me", headers=user_headers).json()["id"]
    path = "/users/me/sport.ics"
    params = {}
    if keyed:
        path = f"/users/{user_id}/sport.ics"
        key = schedule_client.post(
            "/users/me/get-schedule-access-key", params={"resource_path": path}, headers=user_headers
        ).json()["access_key"]["access_key"]
        assert schedule_client.get(path, params={"access_key": "wrong"}).status_code == 403
        params = {"access_key": key}
    with respx.mock(assert_all_called=True) as mock:
        token = mock.get(
            f"{inh_accounts.api_url}/tokens/generate-sport-token", params={"innohassle_id": "test-user-1"}
        ).respond(200, json={"access_token": "sport-token"})
        schedule = mock.get(f"{SPORT_URL}/users/me/schedule").respond(
            200,
            json=[
                _personal_training(32133),
                _personal_training(32134, checked_in=False),
                _personal_training(32135, all_day=True),
            ],
        )
        response = schedule_client.get(path, params=params, headers={} if keyed else user_headers)
    assert token.called
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    request = schedule.calls[0].request
    assert request.headers["authorization"] == "Bearer sport-token"
    start = dtm.datetime.fromisoformat(request.url.params["start"])
    end = dtm.datetime.fromisoformat(request.url.params["end"])
    assert end - start == dtm.timedelta(days=14)
    assert start.tzinfo is not None
    events = icalendar.Calendar.from_ical(response.content).walk("VEVENT")
    assert len(events) == 2
    event = events[0]
    assert str(event["SUMMARY"]) == "Football"
    assert str(event["LOCATION"]) == "[SC] Big Hall"
    assert str(event["UID"]) == f"sport-{crc32(b'32133'):x}@innohassle.ru"
    assert str(event["X-SPORT-TRAINING-ID"]) == "32133"
    assert str(event["X-SPORT-CHECKED-IN"]) == "True"
    assert str(event["X-SPORT-CAN-CHECKIN"]) == "False"
    assert event.decoded("DTSTART") == dtm.datetime(2026, 10, 15, 14, tzinfo=dtm.UTC)
    assert event.decoded("DTEND") == dtm.datetime(2026, 10, 15, 16, tzinfo=dtm.UTC)
    assert "TZID" not in event["DTSTART"].params
    assert "TZID" not in event["DTEND"].params
    assert events[1].decoded("DTSTART") == dtm.date(2026, 10, 15)
    assert events[1].decoded("DTEND") == dtm.date(2026, 10, 16)
    assert "LOCATION" not in events[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,payload,error",
    [(403, {"detail": "Forbidden"}, ApiError), (200, [{"title": "legacy"}], ResponseValidationError)],
)
async def test_sport_v3_rejects_upstream_errors_and_legacy_payload(integrations, status: int, payload, error):
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{inh_accounts.api_url}/tokens/generate-sport-token").respond(
            200, json={"access_token": "sport-token"}
        )
        mock.get(f"{SPORT_URL}/users/me/schedule").respond(status, json=payload)
        with pytest.raises(error):
            await get_personal_sport_ics(_user())


@pytest.mark.asyncio
async def test_sport_requires_linked_account(integrations):
    user = _user().model_copy(update={"innohassle_id": None})
    with pytest.raises(HTTPException, match="User has no innohassle account linked") as error:
        await get_personal_sport_ics(user)
    assert error.value.status_code == 404


def test_sport_defaults_to_v3():
    assert SportSettings().api_url == "https://sport.innopolis.university/api/v3"
