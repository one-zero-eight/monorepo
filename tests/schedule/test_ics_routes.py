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
    schedule_client.post("/users/me/favorites", params={"group_alias": group["alias"]}, headers=user_headers)

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


def test_local_group_ics_keeps_english_for_assistant_member(
    schedule_client: TestClient,
    parser_headers: dict[str, str],
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    ics_dir = tmp_path / "ics"
    ics_dir.mkdir()
    (ics_dir / "core.ics").write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\n"
        "BEGIN:VEVENT\nUID:core@example.com\nDTSTART:20260901T104000Z\nDTEND:20260901T121000Z\n"
        "SUMMARY:Algorithms\nEND:VEVENT\n"
        "BEGIN:VEVENT\nUID:english@example.com\nDTSTART:20260901T142000Z\nDTEND:20260901T155000Z\n"
        "SUMMARY:English for Academic Purposes I\nEND:VEVENT\nEND:VCALENDAR\n",
        encoding="utf-8",
    )
    from src.schedule.config import settings

    monkeypatch.setattr(settings, "predefined_dir", tmp_path)
    create_event_group(schedule_client, parser_headers, alias="core-group", path="core.ics")
    response = schedule_client.get(
        "/core-group.ics",
        params={"user_id": 206527, "export_type": "url"},
    )

    assert response.status_code == 200
    assert b"Algorithms" in response.content
    assert b"English for Academic Purposes" in response.content


def test_event_group_alias_ics_from_assistant(
    schedule_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from src.schedule.config import settings
    from src.schedule.config_schema import ScheduleAssistantIntegrationSettings

    api_url = "https://assistant.test"
    monkeypatch.setattr(
        settings,
        "schedule_assistant",
        ScheduleAssistantIntegrationSettings(api_url=api_url, api_key=SecretStr("service-key")),
    )
    ical = "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n"
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(f"{api_url}/integration/event-groups/virtual-group/schedule.ics").mock(
            return_value=httpx.Response(200, text=ical)
        )
        response = schedule_client.get(
            "/virtual-group.ics",
            params={"user_id": 1, "export_type": "default"},
        )

    assert route.calls[0].request.headers["authorization"] == "Bearer service-key"
    assert response.status_code == 200
    assert response.content.startswith(b"BEGIN:VCALENDAR")


def test_personal_ics_merges_local_and_assistant_groups(
    schedule_client: TestClient,
    parser_headers: dict[str, str],
    user_headers: dict[str, str],
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    from src.schedule.config import settings
    from src.schedule.config_schema import ScheduleAssistantIntegrationSettings

    ics_dir = tmp_path / "ics"
    ics_dir.mkdir()
    (ics_dir / "local.ics").write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\nX-WR-CALNAME:Local\nBEGIN:VEVENT\nUID:local@example.com\n"
        "DTSTART:20250101T100000Z\nDTEND:20250101T110000Z\nSUMMARY:Local\nEND:VEVENT\nEND:VCALENDAR\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "predefined_dir", tmp_path)
    api_url = "https://assistant.test"
    monkeypatch.setattr(
        settings,
        "schedule_assistant",
        ScheduleAssistantIntegrationSettings(api_url=api_url, api_key=SecretStr("service-key")),
    )
    local = create_event_group(schedule_client, parser_headers, alias="local-group", path="local.ics")
    schedule_client.post(
        "/users/me/favorites",
        params={"group_alias": local["alias"]},
        headers=user_headers,
    )
    external = "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:virtual@example.com\nDTSTART:20250101T120000Z\nDTEND:20250101T130000Z\nSUMMARY:Virtual\nEND:VEVENT\nEND:VCALENDAR\n"

    with respx.mock(assert_all_called=True) as mock:
        groups_route = mock.get(f"{api_url}/integration/event-groups").mock(
            return_value=httpx.Response(200, json=[{"alias": "virtual-group", "name": "Virtual"}])
        )
        schedule_client.post(
            "/users/me/favorites",
            params={"group_alias": "virtual-group"},
            headers=user_headers,
        )
        batch_route = mock.post(f"{api_url}/integration/event-groups/schedule.ics").mock(
            return_value=httpx.Response(200, text=external)
        )
        mock.get(f"{api_url}/integration/users/test-user-1@innopolis.university/predefined").mock(
            return_value=httpx.Response(200, json=[])
        )
        response = schedule_client.get("/users/me/all.ics", headers=user_headers)

    assert groups_route.called
    assert batch_route.calls[0].request.content == b'{"aliases":["virtual-group"]}'
    assert response.status_code == 200
    assert b"local@example.com" in response.content
    assert b"virtual@example.com" in response.content


def test_personal_ics_keeps_local_and_assistant_english(
    schedule_client: TestClient,
    parser_headers: dict[str, str],
    user_headers: dict[str, str],
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    from src.schedule.config import settings
    from src.schedule.config_schema import ScheduleAssistantIntegrationSettings

    ics_dir = tmp_path / "ics"
    ics_dir.mkdir()
    (ics_dir / "core.ics").write_text(
        "BEGIN:VCALENDAR\nVERSION:2.0\nX-WR-CALNAME:Core\n"
        "BEGIN:VEVENT\nUID:core@example.com\nDTSTART:20260901T104000Z\nDTEND:20260901T121000Z\n"
        "SUMMARY:Algorithms\nEND:VEVENT\n"
        "BEGIN:VEVENT\nUID:old-english@example.com\nDTSTART:20260901T142000Z\nDTEND:20260901T155000Z\n"
        "SUMMARY:English for Academic Purposes I\nEND:VEVENT\nEND:VCALENDAR\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "predefined_dir", tmp_path)
    api_url = "https://assistant.test"
    monkeypatch.setattr(
        settings,
        "schedule_assistant",
        ScheduleAssistantIntegrationSettings(api_url=api_url, api_key=SecretStr("service-key")),
    )
    local = create_event_group(schedule_client, parser_headers, alias="core-group", path="core.ics")
    schedule_client.post(
        "/users/me/favorites",
        params={"group_alias": local["alias"]},
        headers=user_headers,
    )
    external = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:new-english@example.com\n"
        "DTSTART:20260901T124000Z\nDTEND:20260901T141000Z\n"
        "SUMMARY:Academic Writing and Argumentation I (class)\nEND:VEVENT\nEND:VCALENDAR\n"
    )

    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{api_url}/integration/users/test-user-1@innopolis.university/predefined").mock(
            return_value=httpx.Response(
                200,
                json={"event_groups": ["english-awa-i-1"]},
            )
        )
        mock.post(f"{api_url}/integration/event-groups/schedule.ics").mock(
            return_value=httpx.Response(200, text=external)
        )
        response = schedule_client.get("/users/me/all.ics", headers=user_headers)

    assert response.status_code == 200
    assert b"core@example.com" in response.content
    assert b"old-english@example.com" in response.content
    assert b"new-english@example.com" in response.content


def test_personal_ics_propagates_assistant_failure(
    schedule_client: TestClient,
    user_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    from src.schedule.config import settings
    from src.schedule.config_schema import ScheduleAssistantIntegrationSettings

    api_url = "https://assistant.test"
    monkeypatch.setattr(
        settings,
        "schedule_assistant",
        ScheduleAssistantIntegrationSettings(api_url=api_url, api_key=SecretStr("service-key")),
    )
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{api_url}/integration/event-groups").mock(
            return_value=httpx.Response(200, json=[{"alias": "virtual-group", "name": "Virtual"}])
        )
        schedule_client.post(
            "/users/me/favorites",
            params={"group_alias": "virtual-group"},
            headers=user_headers,
        )
        mock.post(f"{api_url}/integration/event-groups/schedule.ics").mock(
            return_value=httpx.Response(503, text="unavailable")
        )
        mock.get(f"{api_url}/integration/users/test-user-1@innopolis.university/predefined").mock(
            return_value=httpx.Response(200, json=[])
        )
        response = schedule_client.get("/users/me/all.ics", headers=user_headers)

    assert response.status_code == 502
    assert response.json()["detail"] == "Schedule Assistant request failed with status 503"
