from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src.timer.db.models import Timer, TimerParticipant, TimerPermission, TimerUserType


@pytest.fixture
def created_timer(timer_client: TestClient, user_headers: dict[str, str]) -> dict:
    response = timer_client.post(
        "/timers",
        headers=user_headers,
        json={
            "title": "Hackathon",
            "start_time": "2026-10-20T10:00:00+03:00",
            "end_time": "2026-10-20T18:00:00+03:00",
            "checkpoints": [{"title": "Demo", "time": "2026-10-20T17:00:00+03:00"}],
        },
    )
    assert response.status_code == 201, response.text
    timer = response.json()

    async def join():
        async with timer_client.app.state.sql_storage.create_session() as session, session.begin():
            session.add(
                TimerParticipant(
                    timer_id=timer["id"],
                    user_id="joined-user",
                    user_type=TimerUserType.PARTICIPANT,
                    permissions=[TimerPermission.DELETE],
                )
            )

    assert timer_client.portal is not None
    timer_client.portal.call(join)
    return timer


@pytest.mark.parametrize("user_id", ["test-user-1", "joined-user"])
def test_delete_timer_with_permission(
    timer_client: TestClient, auth_header_factory, user_headers: dict[str, str], created_timer: dict, user_id: str
):
    other = timer_client.post(
        "/timers",
        headers=user_headers,
        json={"title": "Other", "start_time": created_timer["start_time"], "end_time": created_timer["end_time"]},
    )
    assert other.status_code == 201
    headers = auth_header_factory(user_id, f"{user_id}@innopolis.university")
    url = f"/timers/{created_timer['id']}"
    response = timer_client.delete(url, headers=headers)
    assert response.status_code == 204, response.text
    assert response.content == b""
    assert timer_client.get(url, headers=user_headers).status_code == 404
    assert timer_client.delete(url, headers=headers).status_code == 404
    assert timer_client.get(f"/timers/{other.json()['id']}", headers=user_headers).status_code == 200

    async def verify_deleted():
        async with timer_client.app.state.sql_storage.create_session() as session:
            assert await session.get(Timer, created_timer["id"]) is None
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(TimerParticipant)
                    .where(TimerParticipant.timer_id == created_timer["id"])
                )
                == 0
            )

    assert timer_client.portal is not None
    timer_client.portal.call(verify_deleted)


@pytest.mark.parametrize("user_id", ["test-user-1", "joined-user"])
@pytest.mark.parametrize("permissions", [[], [TimerPermission.UPDATE]])
def test_delete_timer_requires_delete_permission(
    timer_client: TestClient, auth_header_factory, created_timer: dict, user_id: str, permissions: list
):
    async def change_permissions():
        async with timer_client.app.state.sql_storage.create_session() as session, session.begin():
            participant = await session.get(TimerParticipant, (created_timer["id"], user_id))
            assert participant is not None
            participant.permissions = permissions

    assert timer_client.portal is not None
    timer_client.portal.call(change_permissions)
    headers = auth_header_factory(user_id, f"{user_id}@innopolis.university")
    url = f"/timers/{created_timer['id']}"
    before = timer_client.get(url, headers=headers).json()
    response = timer_client.delete(url, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Timer delete permission required"
    assert timer_client.get(url, headers=headers).json() == before


def test_nonparticipant_cannot_delete_timer(
    timer_client: TestClient, auth_header_factory, user_headers: dict[str, str], created_timer: dict
):
    headers = auth_header_factory("outsider", "outsider@innopolis.university")
    other = timer_client.post(
        "/timers",
        headers=headers,
        json={"title": "Other", "start_time": created_timer["start_time"], "end_time": created_timer["end_time"]},
    )
    assert other.status_code == 201
    url = f"/timers/{created_timer['id']}"
    before = timer_client.get(url, headers=user_headers).json()
    response = timer_client.delete(url, headers=headers, params={"user_id": "test-user-1"})
    assert response.status_code == 404
    assert timer_client.get(url, headers=user_headers).json() == before


def test_delete_missing_timer(timer_client: TestClient, user_headers: dict[str, str]):
    assert timer_client.delete("/timers/9223372036854775807", headers=user_headers).status_code == 404


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_delete_timer_requires_auth(
    timer_client: TestClient, user_headers: dict[str, str], created_timer: dict, headers: dict
):
    url = f"/timers/{created_timer['id']}"
    before = timer_client.get(url, headers=user_headers).json()
    assert timer_client.delete(url, headers=headers).status_code == 401
    assert timer_client.get(url, headers=user_headers).json() == before


@pytest.mark.parametrize(("timer_id", "expected_status"), [("0", 404), ("-1", 404), ("abc", 422)])
def test_delete_timer_handles_unknown_or_noninteger_id(
    timer_client: TestClient, user_headers: dict[str, str], timer_id: str, expected_status: int
):
    assert timer_client.delete(f"/timers/{timer_id}", headers=user_headers).status_code == expected_status


def test_delete_timer_during_update(
    timer_client: TestClient, auth_header_factory, user_headers: dict[str, str], created_timer: dict
):
    url = f"/timers/{created_timer['id']}"
    barrier = Barrier(2, timeout=10)

    def update():
        barrier.wait()
        return timer_client.put(
            url,
            headers=user_headers,
            json={
                "title": "Updated",
                "start_time": created_timer["start_time"],
                "end_time": created_timer["end_time"],
                "checkpoints": [],
            },
        )

    headers = auth_header_factory("joined-user", "joined-user@innopolis.university")

    def delete():
        barrier.wait()
        return timer_client.delete(url, headers=headers)

    with ThreadPoolExecutor(max_workers=2) as executor:
        updating = executor.submit(update)
        deleting = executor.submit(delete)
        assert updating.result(timeout=15).status_code in (200, 404)
        assert deleting.result(timeout=15).status_code == 204
    assert timer_client.get(url, headers=user_headers).status_code == 404
