import datetime as dtm

import pytest
import pytest_asyncio

from src.schedule_assistant.utcnow import utcnow


@pytest_asyncio.fixture
async def preference_fixtures(
    authenticated_client,
    schedule_config_repo,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.moderator_emails",
        ["test@test.com"],
    )
    monkeypatch.setattr(
        "src.schedule_assistant.modules.instructor_preferences.routes.schedule_config_repository",
        schedule_config_repo,
    )

    term = {
        "name": "Fall",
        "semester": {"start_date": "2026-09-01", "end_date": "2026-12-31"},
        "days": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
        "time_slots": [
            {"start_time": "09:00:00", "end_time": "10:30:00"},
            {"start_time": "10:40:00", "end_time": "12:10:00"},
        ],
    }
    await authenticated_client.put("/schedule-config/term", json=term)
    await authenticated_client.post(
        "/schedule-config/instructors",
        json={
            "id": "pi-1",
            "email": "test@test.com",
            "name_en": "Test PI",
            "slot_preferences": [],
        },
    )
    return term


@pytest.mark.asyncio
async def test_get_and_update_my_preferences(authenticated_client, preference_fixtures):
    get_response = await authenticated_client.get("/instructor-preferences/me")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["instructor_id"] == "pi-1"
    assert body["email"] == "test@test.com"

    put_response = await authenticated_client.put(
        "/instructor-preferences/me",
        json={
            "slot_preferences": [
                {
                    "weekday": "MONDAY",
                    "start_time": "09:00:00",
                    "level": "preferred",
                }
            ]
        },
    )
    assert put_response.status_code == 200
    assert put_response.json()["slot_preferences"] == [
        {
            "weekday": "MONDAY",
            "start_time": "09:00:00",
            "level": "preferred",
        }
    ]


@pytest.mark.asyncio
async def test_share_link_roundtrip(authenticated_client, preference_fixtures):
    share = await authenticated_client.post("/instructor-preferences/pi-1/share-link")
    assert share.status_code == 200
    token = share.json()["token"]
    assert "." not in token
    assert 8 <= len(token) <= 16

    get_response = await authenticated_client.get(f"/instructor-preferences/link/{token}")
    assert get_response.status_code == 200
    assert get_response.json()["instructor_id"] == "pi-1"

    put_response = await authenticated_client.put(
        f"/instructor-preferences/link/{token}",
        json={
            "slot_preferences": [
                {
                    "weekday": "TUESDAY",
                    "start_time": "10:40:00",
                    "level": "banned",
                }
            ]
        },
    )
    assert put_response.status_code == 200
    assert put_response.json()["slot_preferences"][0]["level"] == "banned"


@pytest.mark.asyncio
async def test_share_link_reuses_unexpired_key(authenticated_client, preference_fixtures):
    first = await authenticated_client.post("/instructor-preferences/pi-1/share-link")
    second = await authenticated_client.post("/instructor-preferences/pi-1/share-link")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["token"] == second.json()["token"]
    assert first.json()["expires_at"] == second.json()["expires_at"]


@pytest.mark.asyncio
async def test_unknown_and_expired_invite_key(authenticated_client, preference_fixtures):
    from src.schedule_assistant.db.models import PreferenceInviteLinkRow
    from src.schedule_assistant.modules.instructor_preferences.repository import (
        preference_invite_repository,
    )

    unknown = await authenticated_client.get("/instructor-preferences/link/does-not-exist")
    assert unknown.status_code == 404

    invite = preference_invite_repository.get_or_create_for_instructor(
        "pi-1",
        created_by="test@test.com",
    )
    with preference_invite_repository._session() as session:
        row = session.get(PreferenceInviteLinkRow, invite.key)
        assert row is not None
        row.expires_at = utcnow() - dtm.timedelta(hours=1)
        session.commit()

    expired = await authenticated_client.get(f"/instructor-preferences/link/{invite.key}")
    assert expired.status_code == 404
