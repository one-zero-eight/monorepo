import datetime as dtm

import pytest
from fastapi.testclient import TestClient

from src.timer.db.models import TimerParticipant, TimerPermission, TimerUserType
from src.timer.schemas import ViewTimer


@pytest.fixture
def created_timer(timer_client: TestClient, user_headers: dict[str, str]) -> dict:
    response = timer_client.post(
        "/timers",
        headers=user_headers,
        json={
            "title": "Original",
            "start_time": "2026-10-20T10:00:00+03:00",
            "end_time": "2026-10-20T18:00:00+03:00",
            "checkpoints": [
                {"title": "Review", "time": "2026-10-20T12:00:00+03:00"},
                {"title": "Demo", "time": "2026-10-20T17:00:00+03:00"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def update_payload() -> dict:
    return {
        "title": "Updated",
        "start_time": "2026-10-20T11:00:00+03:00",
        "end_time": "2026-10-20T19:00:00+03:00",
        "checkpoints": [
            {"title": "Final review", "time": "2026-10-20T18:00:00+03:00"},
            {"title": "New checkpoint", "time": "2026-10-20T13:00:00+03:00"},
        ],
    }


def set_permissions(client: TestClient, timer_id: int, user_id: str, permissions: list[TimerPermission]):
    async def save():
        async with client.app.state.sql_storage.create_session() as session, session.begin():
            participant = await session.get(TimerParticipant, (timer_id, user_id))
            if participant is None:
                participant = TimerParticipant(timer_id=timer_id, user_id=user_id, user_type=TimerUserType.PARTICIPANT)
                session.add(participant)
            participant.permissions = permissions

    assert client.portal is not None
    client.portal.call(save)


@pytest.mark.parametrize("user_id", ["test-user-1", "joined-user"])
def test_update_timer_with_permission(
    timer_client: TestClient, auth_header_factory, created_timer: dict, update_payload: dict, user_id: str
):
    set_permissions(timer_client, created_timer["id"], user_id, [TimerPermission.UPDATE])
    headers = auth_header_factory(user_id, f"{user_id}@innopolis.university")
    url = f"/timers/{created_timer['id']}"
    before = timer_client.get(url, headers=headers).json()
    response = timer_client.put(url, headers=headers, json=update_payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == created_timer["id"]
    assert data["title"] == "Updated"
    for field in ("start_time", "end_time"):
        assert dtm.datetime.fromisoformat(data[field]) == dtm.datetime.fromisoformat(update_payload[field])
    assert data["created_at"] == before["created_at"]
    assert dtm.datetime.fromisoformat(data["updated_at"]) > dtm.datetime.fromisoformat(before["updated_at"])
    assert sorted(data["participants"], key=lambda item: item["user_id"]) == sorted(
        before["participants"], key=lambda item: item["user_id"]
    )
    assert [point["title"] for point in data["checkpoints"]] == ["New checkpoint", "Final review"]
    assert all(point.keys() == {"title", "time"} for point in data["checkpoints"])
    saved = timer_client.get(url, headers=headers)
    assert saved.status_code == 200
    assert ViewTimer.model_validate(saved.json()) == ViewTimer.model_validate(data)


def test_update_timer_can_remove_all_checkpoints(
    timer_client: TestClient, user_headers: dict[str, str], created_timer: dict, update_payload: dict
):
    url = f"/timers/{created_timer['id']}"
    update_payload["checkpoints"] = []
    response = timer_client.put(url, headers=user_headers, json=update_payload)
    assert response.status_code == 200, response.text
    assert response.json()["checkpoints"] == []
    assert timer_client.get(url, headers=user_headers).json()["checkpoints"] == []


@pytest.mark.parametrize("user_id", ["test-user-1", "joined-user"])
@pytest.mark.parametrize("permissions", [[], [TimerPermission.DELETE]])
def test_update_timer_requires_update_permission(
    timer_client: TestClient,
    auth_header_factory,
    created_timer: dict,
    update_payload: dict,
    user_id: str,
    permissions: list,
):
    set_permissions(timer_client, created_timer["id"], user_id, permissions)
    headers = auth_header_factory(user_id, f"{user_id}@innopolis.university")
    url = f"/timers/{created_timer['id']}"
    before = timer_client.get(url, headers=headers).json()
    response = timer_client.put(url, headers=headers, json=update_payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "Timer update permission required"
    assert timer_client.get(url, headers=headers).json() == before


def test_nonparticipant_cannot_update_timer(
    timer_client: TestClient,
    auth_header_factory,
    user_headers: dict[str, str],
    created_timer: dict,
    update_payload: dict,
):
    headers = auth_header_factory("outsider", "outsider@innopolis.university")
    other = timer_client.post("/timers", headers=headers, json={**update_payload, "checkpoints": []})
    assert other.status_code == 201
    url = f"/timers/{created_timer['id']}"
    before = timer_client.get(url, headers=user_headers).json()
    response = timer_client.put(url, headers=headers, json=update_payload, params={"user_id": "test-user-1"})
    assert response.status_code == 404
    assert timer_client.get(url, headers=user_headers).json() == before


def test_update_missing_timer(timer_client: TestClient, user_headers: dict[str, str], update_payload: dict):
    response = timer_client.put("/timers/9223372036854775807", headers=user_headers, json=update_payload)
    assert response.status_code == 404


@pytest.mark.parametrize(("timer_id", "expected_status"), [("0", 404), ("-1", 404), ("abc", 422)])
def test_update_timer_handles_unknown_or_noninteger_id(
    timer_client: TestClient,
    user_headers: dict[str, str],
    update_payload: dict,
    timer_id: str,
    expected_status: int,
):
    response = timer_client.put(f"/timers/{timer_id}", headers=user_headers, json=update_payload)
    assert response.status_code == expected_status


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_update_timer_requires_auth(timer_client: TestClient, created_timer: dict, update_payload: dict, headers: dict):
    assert timer_client.put(f"/timers/{created_timer['id']}", headers=headers, json=update_payload).status_code == 401


@pytest.mark.parametrize("missing_field", ["title", "start_time", "end_time", "checkpoints"])
def test_update_timer_requires_all_fields(
    timer_client: TestClient,
    user_headers: dict[str, str],
    created_timer: dict,
    update_payload: dict,
    missing_field: str,
):
    del update_payload[missing_field]
    url = f"/timers/{created_timer['id']}"
    before = timer_client.get(url, headers=user_headers).json()
    assert timer_client.put(url, headers=user_headers, json=update_payload).status_code == 422
    assert timer_client.get(url, headers=user_headers).json() == before


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "я" * 201},
        {"title": " "},
        {"title": "Demo\x00title"},
        {"start_time": "0001-01-01T00:10:00+01:00"},
        {"end_time": "9999-12-31T23:20:00-01:00"},
        {"start_time": "0001-01-01T01:00:00+01:00"},
        {"end_time": "9999-12-31T22:59:59.999999-01:00"},
        {"end_time": "2026-10-20T11:00:00+03:00"},
        {"start_time": "2026-10-21T10:00:00+03:00"},
        {"start_time": "2026-10-20T11:00:00"},
        {"checkpoints": [{"title": "Outside", "time": "2026-10-20T20:00:00+03:00"}]},
        {"checkpoints": [{"title": "я" * 201, "time": "2026-10-20T12:00:00+03:00"}]},
        {"checkpoints": [{"title": "Demo", "time": "2026-10-20T12:00:00"}]},
        {"checkpoints": [{"title": "Demo\x00title", "time": "2026-10-20T12:00:00+03:00"}]},
        {"permissions": ["update"]},
        {
            "checkpoints": [
                {"id": "00000000-0000-0000-0000-000000000001", "title": "Demo", "time": "2026-10-20T12:00:00+03:00"}
            ]
        },
    ],
)
def test_update_timer_rejects_invalid_payload(
    timer_client: TestClient, user_headers: dict[str, str], created_timer: dict, update_payload: dict, overrides: dict
):
    url = f"/timers/{created_timer['id']}"
    before = timer_client.get(url, headers=user_headers).json()
    response = timer_client.put(url, headers=user_headers, json=update_payload | overrides)
    assert response.status_code == 422, response.text
    assert timer_client.get(url, headers=user_headers).json() == before
