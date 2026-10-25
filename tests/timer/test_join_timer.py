from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src.timer.db.models import TimerParticipant, TimerPermission, TimerUserType
from src.timer.schemas import ViewTimer


@pytest.fixture
def invitation(timer_client: TestClient, user_headers: dict[str, str]) -> dict:
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
    response = timer_client.post(f"/timers/{timer['id']}/invitations", headers=user_headers)
    assert response.status_code == 201, response.text
    return {"timer": timer, "uuid": response.json()["uuid"]}


def test_join_timer_grants_update_only(timer_client: TestClient, auth_header_factory, invitation: dict):
    headers = auth_header_factory("joined-user", "joined-user@innopolis.university")
    timer = invitation["timer"]
    timer_url = f"/timers/{timer['id']}"
    assert timer_client.get(timer_url, headers=headers).status_code == 404
    response = timer_client.post(
        f"/invitations/{invitation['uuid']}/join",
        headers=headers,
        params={"user_id": "somebody-else", "permissions": "delete,invite"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    for field in ("id", "title", "created_at", "updated_at", "checkpoints"):
        assert data[field] == timer[field]
    memberships = {participant["user_id"]: participant for participant in data["participants"]}
    assert memberships.keys() == {"test-user-1", "joined-user"}
    assert memberships["joined-user"]["user_type"] == "participant"
    assert memberships["joined-user"]["permissions"] == ["update"]
    assert memberships["test-user-1"] == timer["participants"][0]
    assert timer_client.get(timer_url, headers=headers).status_code == 200
    listed = timer_client.get("/timers", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [timer["id"]]

    async def verify_saved():
        async with timer_client.app.state.sql_storage.create_session() as session:
            participant = await session.get(TimerParticipant, (timer["id"], "joined-user"))
            assert participant is not None
            assert participant.user_type == TimerUserType.PARTICIPANT
            assert participant.permissions == [TimerPermission.UPDATE]
            assert participant.joined_at.tzinfo is not None

    assert timer_client.portal is not None
    timer_client.portal.call(verify_saved)
    update_payload = {field: data[field] for field in ("title", "start_time", "end_time", "checkpoints")}
    update_payload["title"] = "Updated by participant"
    assert timer_client.put(timer_url, headers=headers, json=update_payload).status_code == 200
    assert timer_client.delete(timer_url, headers=headers).status_code == 404
    assert timer_client.post(f"{timer_url}/invitations", headers=headers).status_code == 404


def test_invitation_is_reusable_and_join_is_idempotent(timer_client: TestClient, auth_header_factory, invitation: dict):
    url = f"/invitations/{invitation['uuid']}/join"
    headers = auth_header_factory("first-user", "first-user@innopolis.university")
    first = timer_client.post(url, headers=headers)
    repeated = timer_client.post(url, headers=headers)
    assert first.status_code == repeated.status_code == 200
    assert ViewTimer.model_validate(first.json()) == ViewTimer.model_validate(repeated.json())
    other_headers = auth_header_factory("second-user", "second-user@innopolis.university")
    other = timer_client.post(url, headers=other_headers)
    assert other.status_code == 200
    assert len(other.json()["participants"]) == 3
    assert {participant["user_id"] for participant in other.json()["participants"]} == {
        "test-user-1",
        "first-user",
        "second-user",
    }


@pytest.mark.parametrize("user_id", ["test-user-1", "joined-user"])
def test_rejoin_preserves_role_permissions_and_join_time(
    timer_client: TestClient, auth_header_factory, invitation: dict, user_id: str
):
    headers = auth_header_factory(user_id, f"{user_id}@innopolis.university")
    url = f"/invitations/{invitation['uuid']}/join"
    assert timer_client.post(url, headers=headers).status_code == 200
    if user_id == "joined-user":

        async def remove_update_permission():
            async with timer_client.app.state.sql_storage.create_session() as session, session.begin():
                participant = await session.get(TimerParticipant, (invitation["timer"]["id"], user_id))
                assert participant is not None
                participant.permissions = []

        assert timer_client.portal is not None
        timer_client.portal.call(remove_update_permission)
    before = timer_client.get(f"/timers/{invitation['timer']['id']}", headers=headers).json()
    response = timer_client.post(url, headers=headers)
    assert response.status_code == 200
    assert ViewTimer.model_validate(response.json()) == ViewTimer.model_validate(before)


def test_concurrent_join_through_different_invitations(
    timer_client: TestClient, user_headers: dict[str, str], auth_header_factory, invitation: dict
):
    second = timer_client.post(f"/timers/{invitation['timer']['id']}/invitations", headers=user_headers)
    assert second.status_code == 201
    headers = auth_header_factory("joined-user", "joined-user@innopolis.university")
    barrier = Barrier(2, timeout=10)

    def join(code: str):
        barrier.wait()
        return timer_client.post(f"/invitations/{code}/join", headers=headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_request = executor.submit(join, invitation["uuid"])
        second_request = executor.submit(join, second.json()["uuid"])
        first_response = first_request.result(timeout=15)
        second_response = second_request.result(timeout=15)
    assert first_response.status_code == second_response.status_code == 200
    assert ViewTimer.model_validate(first_response.json()) == ViewTimer.model_validate(second_response.json())
    assert len(first_response.json()["participants"]) == 2


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_join_timer_requires_auth(timer_client: TestClient, invitation: dict, headers: dict):
    assert timer_client.post(f"/invitations/{invitation['uuid']}/join", headers=headers).status_code == 401
    assert_participant_count(timer_client, 1)


def test_unknown_invitation_does_not_join(timer_client: TestClient, user_headers: dict[str, str], invitation: dict):
    response = timer_client.post(f"/invitations/{uuid4()}/join", headers=user_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Invitation not found"
    assert_participant_count(timer_client, 1)


def test_invalid_invitation_uuid(timer_client: TestClient, user_headers: dict[str, str]):
    assert timer_client.post("/invitations/not-a-uuid/join", headers=user_headers).status_code == 422
    assert_participant_count(timer_client, 0)


def test_deleted_timer_invitation_is_invalid(timer_client: TestClient, user_headers: dict[str, str], invitation: dict):
    assert timer_client.delete(f"/timers/{invitation['timer']['id']}", headers=user_headers).status_code == 204
    assert timer_client.post(f"/invitations/{invitation['uuid']}/join", headers=user_headers).status_code == 404
    assert_participant_count(timer_client, 0)


def test_join_during_timer_deletion(
    timer_client: TestClient, user_headers: dict[str, str], auth_header_factory, invitation: dict
):
    barrier = Barrier(2, timeout=10)
    participant_headers = auth_header_factory("joined-user", "joined-user@innopolis.university")

    def join():
        barrier.wait()
        return timer_client.post(f"/invitations/{invitation['uuid']}/join", headers=participant_headers)

    def delete():
        barrier.wait()
        return timer_client.delete(f"/timers/{invitation['timer']['id']}", headers=user_headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        joining = executor.submit(join)
        deleting = executor.submit(delete)
        assert joining.result(timeout=15).status_code in (200, 404)
        assert deleting.result(timeout=15).status_code == 204
    assert timer_client.get("/timers", headers=participant_headers).json() == []
    assert_participant_count(timer_client, 0)


def assert_participant_count(client: TestClient, count: int):
    async def verify():
        async with client.app.state.sql_storage.create_session() as session:
            assert await session.scalar(select(func.count()).select_from(TimerParticipant)) == count

    assert client.portal is not None
    client.portal.call(verify)
