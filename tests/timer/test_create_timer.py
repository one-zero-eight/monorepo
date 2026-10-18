import datetime as dtm

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.timer.db.models import Timer, TimerCheckpoint, TimerParticipant
from src.timer.schemas import ViewTimer


@pytest.fixture
def timer_payload() -> dict:
    return {
        "title": "Release sprint",
        "start_time": "2026-10-20T10:00:00+03:00",
        "end_time": "2026-10-20T18:00:00+03:00",
    }


@pytest.mark.parametrize("with_checkpoints", [False, True])
def test_create_timer(
    timer_client: TestClient, user_headers: dict[str, str], timer_payload: dict, with_checkpoints: bool
):
    if with_checkpoints:
        timer_payload["checkpoints"] = [
            {"title": "Demo", "time": timer_payload["end_time"]},
            {"title": "Start", "time": timer_payload["start_time"]},
        ]
    response = timer_client.post("/timers", json=timer_payload, headers=user_headers)
    assert response.status_code == 201, response.text
    data = response.json()
    assert isinstance(data["id"], int)
    assert data["title"] == timer_payload["title"]
    assert dtm.datetime.fromisoformat(data["start_time"]) == dtm.datetime.fromisoformat(timer_payload["start_time"])
    assert dtm.datetime.fromisoformat(data["end_time"]) == dtm.datetime.fromisoformat(timer_payload["end_time"])
    assert dtm.datetime.fromisoformat(data["created_at"]).tzinfo is not None
    assert data["updated_at"] == data["created_at"]
    assert len(data["participants"]) == 1
    creator = data["participants"][0]
    assert creator["user_id"] == "test-user-1"
    assert creator["user_type"] == "creator"
    assert creator["permissions"] == ["update", "delete"]
    assert dtm.datetime.fromisoformat(creator["joined_at"]).tzinfo is not None
    assert [checkpoint["title"] for checkpoint in data["checkpoints"]] == (
        ["Start", "Demo"] if with_checkpoints else []
    )

    async def verify_saved():
        async with timer_client.app.state.sql_storage.create_session() as session:
            saved = await session.scalar(
                select(Timer)
                .where(Timer.id == data["id"])
                .options(selectinload(Timer.participants), selectinload(Timer.checkpoints))
            )
            assert saved is not None
            assert ViewTimer.model_validate(saved) == ViewTimer.model_validate(data)

    assert timer_client.portal is not None
    timer_client.portal.call(verify_saved)


@pytest.mark.parametrize("target", ["timer", "checkpoint"])
def test_create_timer_accepts_200_character_title(
    timer_client: TestClient, user_headers: dict[str, str], timer_payload: dict, target: str
):
    title = "я" * 200
    if target == "timer":
        timer_payload["title"] = title
    else:
        timer_payload["checkpoints"] = [{"title": title, "time": timer_payload["start_time"]}]
    response = timer_client.post("/timers", json=timer_payload, headers=user_headers)
    assert response.status_code == 201, response.text
    result = response.json()
    assert (result["title"] if target == "timer" else result["checkpoints"][0]["title"]) == title


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_create_timer_requires_auth(timer_client: TestClient, timer_payload: dict, headers: dict[str, str]):
    response = timer_client.post("/timers", json=timer_payload, headers=headers)
    assert response.status_code == 401
    assert_no_timers(timer_client)


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "я" * 201},
        {"title": "   "},
        {"end_time": "2026-10-20T10:00:00+03:00"},
        {"end_time": "2026-10-19T18:00:00+03:00"},
        {"start_time": "2026-10-20T10:00:00"},
        {"end_time": "2026-10-20T18:00:00"},
        {"checkpoints": [{"title": "Demo", "time": "2026-10-20T18:00:00"}]},
        {"checkpoints": [{"title": "Demo", "time": "2026-10-20T09:59:00+03:00"}]},
        {"checkpoints": [{"title": "Demo", "time": "2026-10-20T18:01:00+03:00"}]},
        {"checkpoints": [{"title": "я" * 201, "time": "2026-10-20T12:00:00+03:00"}]},
        {"checkpoints": [{"title": " ", "time": "2026-10-20T12:00:00+03:00"}]},
        {"user_creator": "another-user"},
        {"participants": [{"user_id": "another-user", "user_type": "creator", "permissions": ["delete"]}]},
    ],
)
def test_create_timer_rejects_invalid_payload(
    timer_client: TestClient, user_headers: dict[str, str], timer_payload: dict, overrides: dict
):
    response = timer_client.post("/timers", json=timer_payload | overrides, headers=user_headers)
    assert response.status_code == 422, response.text
    assert_no_timers(timer_client)


def assert_no_timers(client: TestClient) -> None:
    async def verify_empty():
        async with client.app.state.sql_storage.create_session() as session:
            for model in (Timer, TimerParticipant, TimerCheckpoint):
                assert await session.scalar(select(func.count()).select_from(model)) == 0

    assert client.portal is not None
    client.portal.call(verify_empty)
