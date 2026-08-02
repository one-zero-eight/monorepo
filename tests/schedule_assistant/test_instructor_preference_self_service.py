import datetime as dtm

import pytest
from pydantic import SecretStr

from src.schedule_assistant.modules.instructor_preferences.tokens import (
    PreferenceTokenPayload,
    sign_preference_token,
    verify_preference_token,
)


@pytest.fixture
async def preference_fixtures(authenticated_client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.moderator_emails",
        ["test@test.com"],
    )
    monkeypatch.setattr(
        "src.schedule_assistant.config.settings.preference_link_secret",
        SecretStr("test-pref-secret"),
    )
    monkeypatch.setattr(
        "src.schedule_assistant.modules.instructor_preferences.tokens.settings.preference_link_secret",
        SecretStr("test-pref-secret"),
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


def test_preference_token_expiry(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "src.schedule_assistant.modules.instructor_preferences.tokens.settings.preference_link_secret",
        SecretStr("test-pref-secret"),
    )
    expired = PreferenceTokenPayload(
        instructor_id="pi-1",
        exp=int((dtm.datetime.now(dtm.UTC) - dtm.timedelta(hours=1)).timestamp()),
    )
    token = sign_preference_token(expired)
    assert verify_preference_token(token) is None

    valid = PreferenceTokenPayload(
        instructor_id="pi-1",
        exp=int((dtm.datetime.now(dtm.UTC) + dtm.timedelta(hours=1)).timestamp()),
    )
    assert verify_preference_token(sign_preference_token(valid)) == valid
