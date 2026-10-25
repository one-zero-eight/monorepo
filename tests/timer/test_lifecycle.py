import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src.timer.db.models import Invitation, Timer, TimerParticipant
from src.timer.schemas import ViewTimer


@pytest.fixture
def timer_with_invitation(timer_client: TestClient, user_headers: dict[str, str]) -> dict:
    created = timer_client.post(
        "/timers",
        headers=user_headers,
        json={
            "title": "Hackathon",
            "start_time": "2026-10-20T10:00:00+03:00",
            "end_time": "2026-10-20T18:00:00+03:00",
            "checkpoints": [{"title": "Demo", "time": "2026-10-20T17:00:00+03:00"}],
        },
    )
    assert created.status_code == 201, created.text
    timer = created.json()
    invitation = timer_client.post(f"/timers/{timer['id']}/invitations", headers=user_headers)
    assert invitation.status_code == 201, invitation.text
    return {"timer": timer, "invitation": invitation.json()}


def test_shared_timer_lifecycle(
    timer_client: TestClient, user_headers: dict[str, str], auth_header_factory, timer_with_invitation: dict
):
    timer = timer_with_invitation["timer"]
    url = f"/timers/{timer['id']}"
    join_url = f"/invitations/{timer_with_invitation['invitation']['uuid']}/join"
    participant_headers = auth_header_factory("participant", "participant@innopolis.university")
    assert timer_client.get("/timers", headers=participant_headers).json() == []
    assert timer_client.post(join_url, headers=participant_headers).status_code == 200

    updated = timer_client.put(
        url,
        headers=participant_headers,
        json={
            "title": "Release sprint",
            "start_time": "2026-10-21T10:00:00+03:00",
            "end_time": "2026-10-21T20:00:00+03:00",
            "checkpoints": [
                {"title": "Final presentation", "time": "2026-10-21T19:00:00+03:00"},
                {"title": "Architecture", "time": "2026-10-21T12:00:00+03:00"},
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    creator_view = timer_client.get(url, headers=user_headers)
    assert creator_view.status_code == 200
    assert creator_view.json()["title"] == "Release sprint"
    assert [point["title"] for point in creator_view.json()["checkpoints"]] == ["Architecture", "Final presentation"]
    for headers in (user_headers, participant_headers):
        listed = timer_client.get("/timers", headers=headers)
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [timer["id"]]
    assert timer_client.delete(url, headers=participant_headers).status_code == 404
    assert timer_client.post(f"{url}/invitations", headers=participant_headers).status_code == 404
    assert timer_client.delete(url, headers=user_headers).status_code == 204
    for headers in (user_headers, participant_headers):
        assert timer_client.get(url, headers=headers).status_code == 404
        assert timer_client.get("/timers", headers=headers).json() == []
    assert timer_client.post(join_url, headers=participant_headers).status_code == 404

    async def verify_cascade():
        async with timer_client.app.state.sql_storage.create_session() as session:
            for model in (Timer, TimerParticipant, Invitation):
                assert await session.scalar(select(func.count()).select_from(model)) == 0

    assert timer_client.portal is not None
    timer_client.portal.call(verify_cascade)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/timers"),
        ("GET", "/timers"),
        ("GET", "/timers/{timer_id}"),
        ("PUT", "/timers/{timer_id}"),
        ("DELETE", "/timers/{timer_id}"),
        ("POST", "/timers/{timer_id}/invitations"),
        ("POST", "/invitations/{uuid}/join"),
    ],
)
def test_expired_token_cannot_access_timer_api(
    timer_client: TestClient,
    user_headers: dict[str, str],
    auth_header_factory,
    timer_with_invitation: dict,
    method: str,
    path: str,
):
    timer = timer_with_invitation["timer"]
    url = path.format(timer_id=timer["id"], uuid=timer_with_invitation["invitation"]["uuid"])
    headers = auth_header_factory("test-user-1", "test-user-1@innopolis.university", expires_in_seconds=-3600)
    payload = {field: timer[field] for field in ("title", "start_time", "end_time", "checkpoints")}
    response = timer_client.request(
        method,
        url,
        headers=headers,
        json=payload if path == "/timers" and method == "POST" or method == "PUT" else None,
    )
    assert response.status_code == 401, response.text
    unchanged = timer_client.get(f"/timers/{timer['id']}", headers=user_headers)
    assert unchanged.status_code == 200
    assert ViewTimer.model_validate(unchanged.json()) == ViewTimer.model_validate(timer)

    async def verify_counts():
        async with timer_client.app.state.sql_storage.create_session() as session:
            for model in (Timer, TimerParticipant, Invitation):
                assert await session.scalar(select(func.count()).select_from(model)) == 1

    assert timer_client.portal is not None
    timer_client.portal.call(verify_counts)
