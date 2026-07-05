import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from tests.schedule.conftest import create_event_group


def test_personal_all_ics_requires_auth(schedule_client: TestClient):
    response = schedule_client.get("/users/me/all.ics")
    assert response.status_code == 401


def test_personal_all_ics_with_favorites(
    schedule_client: TestClient,
    parser_headers: dict[str, str],
    user_headers: dict[str, str],
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    from src.schedule.config import settings

    ics_dir = tmp_path / "ics"
    ics_dir.mkdir()
    ics_path = ics_dir / "favorite.ics"
    ics_path.write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\nX-WR-CALNAME:Test Calendar\nBEGIN:VEVENT\nUID:test@example.com\n"
        "DTSTART:20250101T100000Z\nDTEND:20250101T110000Z\nSUMMARY:Test\nEND:VEVENT\nEND:VCALENDAR\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "predefined_dir", tmp_path)

    group = create_event_group(
        schedule_client,
        parser_headers,
        alias="ics-favorite-group",
        path="favorite.ics",
    )
    schedule_client.get("/users/me", headers=user_headers)
    schedule_client.post("/users/me/favorites", params={"group_id": group["id"]}, headers=user_headers)

    response = schedule_client.get("/users/me/all.ics", headers=user_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    body = b"".join(response.iter_bytes())
    assert b"BEGIN:VCALENDAR" in body


def test_workshops_ics_not_configured(schedule_client: TestClient):
    response = schedule_client.get("/workshops.ics")
    assert response.status_code == 404
    assert response.json()["detail"] == "Workshops are not configured"


def test_workshops_ics_proxies_api(schedule_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from src.schedule.config import settings
    from src.schedule.config_schema import WorkshopsSettings

    api_url = "https://workshops.test"
    monkeypatch.setattr(
        settings,
        "workshops",
        WorkshopsSettings(api_url=api_url, api_key=SecretStr("workshops-key")),
    )

    workshop = {
        "id": "workshop-1",
        "english_name": "Test Workshop",
        "dtstart": "2025-01-01T10:00:00+00:00",
        "dtend": "2025-01-01T11:00:00+00:00",
        "is_draft": False,
        "is_active": True,
        "is_approved": True,
    }

    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{api_url}/workshops/").mock(return_value=httpx.Response(200, json=[workshop]))
        response = schedule_client.get("/workshops.ics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert b"BEGIN:VCALENDAR" in response.content


def test_music_room_ics_not_configured(schedule_client: TestClient):
    response = schedule_client.get("/music-room.ics")
    assert response.status_code == 404
    assert response.json()["detail"] == "Music room is not configured"


def test_music_room_ics_proxies_api(schedule_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from src.schedule.config import settings
    from src.schedule.config_schema import MusicRoomSettings

    api_url = "https://music-room.test"
    monkeypatch.setattr(
        settings,
        "music_room",
        MusicRoomSettings(api_url=api_url, api_key=SecretStr("music-room-key")),
    )

    ical = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:music@example.com\n"
        "DTSTART:20250101T100000Z\nDTEND:20250101T110000Z\nSUMMARY:Room\nEND:VEVENT\nEND:VCALENDAR\n"
    )

    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{api_url}/music-room.ics").mock(return_value=httpx.Response(200, text=ical))
        response = schedule_client.get("/music-room.ics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    body = b"".join(response.iter_bytes())
    assert b"BEGIN:VCALENDAR" in body


def test_event_group_alias_ics_from_disk(
    schedule_client: TestClient,
    parser_headers: dict[str, str],
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    from src.schedule.config import settings

    ics_dir = tmp_path / "ics"
    ics_dir.mkdir()
    ics_path = ics_dir / "group.ics"
    ics_path.write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:group@example.com\n"
        "DTSTART:20250101T100000Z\nDTEND:20250101T110000Z\nSUMMARY:Group\nEND:VEVENT\nEND:VCALENDAR\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "predefined_dir", tmp_path)

    create_event_group(
        schedule_client,
        parser_headers,
        alias="disk-ics-group",
        path="group.ics",
    )

    response = schedule_client.get(
        "/disk-ics-group.ics",
        params={"user_id": 1, "export_type": "default"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert b"BEGIN:VCALENDAR" in response.content
