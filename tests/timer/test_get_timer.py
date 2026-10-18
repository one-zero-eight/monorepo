import pytest
from fastapi.testclient import TestClient

from src.timer.db.models import TimerParticipant, TimerUserType
from src.timer.schemas import ViewTimer


@pytest.fixture(params=[False, True], ids=["no-checkpoints", "with-checkpoints"])
def created_timer(request: pytest.FixtureRequest, timer_client: TestClient, user_headers: dict[str, str]) -> dict:
    payload = {
        "title": "Release sprint",
        "start_time": "2026-10-20T10:00:00+03:00",
        "end_time": "2026-10-20T18:00:00+03:00",
        "checkpoints": [
            {"title": "Demo", "time": "2026-10-20T17:00:00+03:00"},
            {"title": "Review", "time": "2026-10-20T12:00:00+03:00"},
        ]
        if request.param
        else [],
    }
    response = timer_client.post("/timers", json=payload, headers=user_headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_creator_can_get_timer(timer_client: TestClient, user_headers: dict[str, str], created_timer: dict):
    response = timer_client.get(f"/timers/{created_timer['id']}", headers=user_headers)
    assert response.status_code == 200, response.text
    assert ViewTimer.model_validate(response.json()) == ViewTimer.model_validate(created_timer)


def test_participant_can_get_timer_without_edit_permissions(
    timer_client: TestClient, auth_header_factory, created_timer: dict
):
    async def join():
        async with timer_client.app.state.sql_storage.create_session() as session, session.begin():
            session.add(
                TimerParticipant(
                    timer_id=created_timer["id"],
                    user_id="joined-user",
                    user_type=TimerUserType.PARTICIPANT,
                    permissions=[],
                )
            )

    assert timer_client.portal is not None
    timer_client.portal.call(join)
    headers = auth_header_factory("joined-user", "joined-user@innopolis.university")
    response = timer_client.get(f"/timers/{created_timer['id']}", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == created_timer["id"]
    assert data["title"] == created_timer["title"]
    assert ViewTimer.model_validate(data).checkpoints == ViewTimer.model_validate(created_timer).checkpoints
    participants = {participant["user_id"]: participant for participant in data["participants"]}
    assert len(data["participants"]) == 2
    assert participants.keys() == {"test-user-1", "joined-user"}
    assert participants["joined-user"]["permissions"] == []
    assert participants["joined-user"]["user_type"] == "participant"


def test_nonparticipant_cannot_get_timer(timer_client: TestClient, auth_header_factory, created_timer: dict):
    headers = auth_header_factory("outsider", "outsider@innopolis.university")
    # Owning a different timer must not grant access to this one.
    own_timer = timer_client.post(
        "/timers",
        headers=headers,
        json={"title": "Other", "start_time": created_timer["start_time"], "end_time": created_timer["end_time"]},
    )
    assert own_timer.status_code == 201
    response = timer_client.get(f"/timers/{created_timer['id']}", headers=headers, params={"user_id": "test-user-1"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Timer not found"


def test_missing_timer_returns_404(timer_client: TestClient, user_headers: dict[str, str]):
    response = timer_client.get("/timers/9223372036854775807", headers=user_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Timer not found"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_get_timer_requires_auth(timer_client: TestClient, headers: dict[str, str]):
    assert timer_client.get("/timers/1", headers=headers).status_code == 401


@pytest.mark.parametrize("timer_id", ["0", "-1", "abc", "9223372036854775808"])
def test_get_timer_rejects_invalid_id(timer_client: TestClient, user_headers: dict[str, str], timer_id: str):
    assert timer_client.get(f"/timers/{timer_id}", headers=user_headers).status_code == 422
