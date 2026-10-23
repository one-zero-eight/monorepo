from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src.timer.db.models import Invitation, TimerParticipant, TimerPermission, TimerUserType


@pytest.fixture
def created_timer(timer_client: TestClient, user_headers: dict[str, str]) -> dict:
    response = timer_client.post(
        "/timers",
        headers=user_headers,
        json={"title": "Hackathon", "start_time": "2026-10-20T10:00:00+03:00", "end_time": "2026-10-20T18:00:00+03:00"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_creator_generates_distinct_uuid4_invitations(
    timer_client: TestClient, user_headers: dict[str, str], created_timer: dict
):
    assert "invite" in created_timer["participants"][0]["permissions"]
    timer_url = f"/timers/{created_timer['id']}"
    before = timer_client.get(timer_url, headers=user_headers).json()
    invitation_ids = []
    for _ in range(2):
        response = timer_client.post(f"{timer_url}/invitations", headers=user_headers)
        assert response.status_code == 201, response.text
        data = response.json()
        assert data.keys() == {"uuid", "timer_id"}
        assert data["timer_id"] == created_timer["id"]
        invitation_id = UUID(data["uuid"])
        assert invitation_id.version == 4
        invitation_ids.append(invitation_id)
    assert len(set(invitation_ids)) == 2
    assert timer_client.get(timer_url, headers=user_headers).json() == before

    async def verify_saved():
        async with timer_client.app.state.sql_storage.create_session() as session:
            invitations = (await session.scalars(select(Invitation))).all()
            assert {invitation.uuid for invitation in invitations} == set(invitation_ids)
            assert all(invitation.timer_id == created_timer["id"] for invitation in invitations)

    assert timer_client.portal is not None
    timer_client.portal.call(verify_saved)

    assert timer_client.delete(timer_url, headers=user_headers).status_code == 204
    assert_no_invitations(timer_client)


@pytest.mark.parametrize(
    ("user_id", "permissions"),
    [
        ("test-user-1", []),
        ("test-user-1", [TimerPermission.UPDATE, TimerPermission.DELETE]),
        ("joined-user", []),
        ("joined-user", [TimerPermission.INVITE]),
        ("joined-user", list(TimerPermission)),
    ],
)
def test_invitation_requires_creator_and_invite_permission(
    timer_client: TestClient, auth_header_factory, created_timer: dict, user_id: str, permissions: list[TimerPermission]
):
    async def set_permissions():
        async with timer_client.app.state.sql_storage.create_session() as session, session.begin():
            participant = await session.get(TimerParticipant, (created_timer["id"], user_id))
            if participant is None:
                participant = TimerParticipant(
                    timer_id=created_timer["id"], user_id=user_id, user_type=TimerUserType.PARTICIPANT
                )
                session.add(participant)
            participant.permissions = permissions

    assert timer_client.portal is not None
    timer_client.portal.call(set_permissions)
    headers = auth_header_factory(user_id, f"{user_id}@innopolis.university")
    response = timer_client.post(f"/timers/{created_timer['id']}/invitations", headers=headers)
    assert response.status_code == 403
    assert_no_invitations(timer_client)


def test_other_creator_cannot_invite_to_timer(timer_client: TestClient, auth_header_factory, created_timer: dict):
    headers = auth_header_factory("outsider", "outsider@innopolis.university")
    other = timer_client.post(
        "/timers",
        headers=headers,
        json={"title": "Other", "start_time": created_timer["start_time"], "end_time": created_timer["end_time"]},
    )
    assert other.status_code == 201
    response = timer_client.post(
        f"/timers/{created_timer['id']}/invitations", headers=headers, params={"user_id": "test-user-1"}
    )
    assert response.status_code == 404
    assert_no_invitations(timer_client)


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_create_invitation_requires_auth(timer_client: TestClient, created_timer: dict, headers: dict):
    assert timer_client.post(f"/timers/{created_timer['id']}/invitations", headers=headers).status_code == 401
    assert_no_invitations(timer_client)


def test_create_invitation_for_missing_timer(timer_client: TestClient, user_headers: dict[str, str]):
    assert timer_client.post("/timers/9223372036854775807/invitations", headers=user_headers).status_code == 404
    assert_no_invitations(timer_client)


@pytest.mark.parametrize("timer_id", ["0", "-1", "abc", "9223372036854775808"])
def test_create_invitation_rejects_invalid_timer_id(
    timer_client: TestClient, user_headers: dict[str, str], timer_id: str
):
    assert timer_client.post(f"/timers/{timer_id}/invitations", headers=user_headers).status_code == 422
    assert_no_invitations(timer_client)


def assert_no_invitations(client: TestClient):
    async def verify_empty():
        async with client.app.state.sql_storage.create_session() as session:
            assert await session.scalar(select(func.count()).select_from(Invitation)) == 0

    assert client.portal is not None
    client.portal.call(verify_empty)
