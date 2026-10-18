import datetime as dtm

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from src.timer.db.models import Timer, TimerParticipant, TimerUserType


def test_list_timers_is_empty(timer_client: TestClient, user_headers: dict[str, str]):
    response = timer_client.get("/timers", headers=user_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_list_timers_requires_auth(timer_client: TestClient, headers: dict[str, str]):
    assert timer_client.get("/timers", headers=headers).status_code == 401


def test_list_created_and_joined_timers(timer_client: TestClient, user_headers: dict[str, str], auth_header_factory):
    other_headers = auth_header_factory("other-user", "other-user@innopolis.university")
    payload = {
        "title": "Hackathon",
        "start_time": "2026-10-20T10:00:00+03:00",
        "end_time": "2026-10-20T18:00:00+03:00",
        "checkpoints": [{"title": "Demo", "time": "2026-10-20T17:00:00+03:00"}],
    }
    timers = []
    for title, headers in [
        ("Owned first", user_headers),
        ("Owned second", user_headers),
        ("Joined", other_headers),
        ("Private", other_headers),
    ]:
        response = timer_client.post("/timers", headers=headers, json=payload | {"title": title})
        assert response.status_code == 201, response.text
        timers.append(response.json())
    first, second, joined, private = timers

    async def prepare_memberships():
        async with timer_client.app.state.sql_storage.create_session() as session, session.begin():
            session.add_all(
                [
                    TimerParticipant(
                        timer_id=joined["id"],
                        user_id="test-user-1",
                        user_type=TimerUserType.PARTICIPANT,
                        permissions=[],
                    ),
                    TimerParticipant(
                        timer_id=first["id"], user_id="other-user", user_type=TimerUserType.PARTICIPANT, permissions=[]
                    ),
                ]
            )
            # Equal creation times must still produce a stable order by ID.
            await session.execute(
                update(Timer)
                .where(Timer.id.in_([timer["id"] for timer in timers]))
                .values(created_at=dtm.datetime(2026, 10, 18, 10, tzinfo=dtm.UTC))
            )
            # The oldest ID is the newest timer: creation time takes priority over ID.
            await session.execute(
                update(Timer)
                .where(Timer.id == first["id"])
                .values(created_at=dtm.datetime(2026, 10, 19, 10, tzinfo=dtm.UTC))
            )

    assert timer_client.portal is not None
    timer_client.portal.call(prepare_memberships)
    response = timer_client.get("/timers", headers=user_headers, params={"user_id": "other-user"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert [timer["id"] for timer in data] == [first["id"], joined["id"], second["id"]]
    assert [timer["title"] for timer in data] == ["Owned first", "Joined", "Owned second"]
    for timer in data:
        assert timer["checkpoints"] == payload["checkpoints"]
        assert dtm.datetime.fromisoformat(timer["start_time"]) == dtm.datetime.fromisoformat(payload["start_time"])
        assert dtm.datetime.fromisoformat(timer["end_time"]) == dtm.datetime.fromisoformat(payload["end_time"])
        assert dtm.datetime.fromisoformat(timer["updated_at"]).tzinfo is not None
    memberships = {participant["user_id"]: participant for participant in data[1]["participants"]}
    assert memberships.keys() == {"test-user-1", "other-user"}
    assert memberships["test-user-1"]["user_type"] == "participant"
    assert memberships["test-user-1"]["permissions"] == []

    # A user without membership sees nothing, even if another user ID is supplied.
    stranger_headers = auth_header_factory("stranger", "stranger@innopolis.university")
    stranger_response = timer_client.get("/timers", headers=stranger_headers, params={"user_id": "test-user-1"})
    assert stranger_response.status_code == 200
    assert stranger_response.json() == []

    assert timer_client.delete(f"/timers/{first['id']}", headers=user_headers).status_code == 204
    assert timer_client.delete(f"/timers/{joined['id']}", headers=other_headers).status_code == 204
    remaining = timer_client.get("/timers", headers=user_headers)
    assert remaining.status_code == 200
    assert [timer["id"] for timer in remaining.json()] == [second["id"]]
    assert timer_client.get(f"/timers/{private['id']}", headers=other_headers).status_code == 200
