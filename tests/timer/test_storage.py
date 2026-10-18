import datetime as dtm
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Connection, delete, inspect, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import selectinload

from src.timer.db.models import Timer, TimerCheckpoint, TimerParticipant, TimerPermission, TimerUserType


def make_timer(**overrides) -> Timer:
    values = {
        "title": "Release sprint",
        "start_time": dtm.datetime(2026, 10, 17, 10, tzinfo=dtm.UTC),
        "end_time": dtm.datetime(2026, 10, 18, 10, tzinfo=dtm.UTC),
    }
    return Timer(**(values | overrides))


def test_store_timer_and_repeat_migration(timer_client: TestClient):
    async def exercise():
        storage = timer_client.app.state.sql_storage
        async with storage.create_session() as session:
            timer = make_timer(
                participants=[
                    TimerParticipant(
                        user_id="creator",
                        user_type=TimerUserType.CREATOR,
                        permissions=[TimerPermission.UPDATE, TimerPermission.DELETE],
                    ),
                    TimerParticipant(user_id="participant", user_type=TimerUserType.PARTICIPANT),
                ],
                checkpoints=[TimerCheckpoint(title="Demo", time=dtm.datetime(2026, 10, 18, 9, tzinfo=dtm.UTC))],
            )
            session.add(timer)
            await session.commit()
            timer_id = timer.id
            assert isinstance(timer_id, int)

        def verify_schema(connection: Connection):
            config = Config(Path(__file__).parents[2] / "src/timer/alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            command.check(config)
            indexes = inspect(connection).get_indexes("timer_participants")
            assert any(index["column_names"] == ["user_id"] for index in indexes)

        async with storage.engine.begin() as connection:
            await connection.run_sync(verify_schema)

        async with storage.create_session() as session:
            saved = await session.scalar(
                select(Timer)
                .where(Timer.id == timer_id)
                .options(selectinload(Timer.participants), selectinload(Timer.checkpoints))
            )
            assert saved is not None
            assert saved.title == "Release sprint"
            assert saved.start_time == dtm.datetime(2026, 10, 17, 10, tzinfo=dtm.UTC)
            assert saved.created_at.tzinfo is not None
            assert saved.updated_at.tzinfo is not None
            participants = {item.user_id: item for item in saved.participants}
            assert participants["creator"].permissions == [TimerPermission.UPDATE, TimerPermission.DELETE]
            assert participants["participant"].permissions == []
            assert participants["participant"].joined_at.tzinfo is not None
            assert isinstance(saved.checkpoints[0].id, UUID)
            assert saved.checkpoints[0].title == "Demo"
            participants["participant"].permissions.append(TimerPermission.UPDATE)
            await session.commit()

        async with storage.create_session() as session:
            participant = await session.get(TimerParticipant, (timer_id, "participant"))
            assert participant is not None
            assert participant.permissions == [TimerPermission.UPDATE]
            await session.execute(delete(Timer).where(Timer.id == timer_id))
            await session.commit()

        async with storage.create_session() as session:
            assert await session.scalar(select(TimerParticipant)) is None
            assert await session.scalar(select(TimerCheckpoint)) is None

    assert timer_client.portal is not None
    timer_client.portal.call(exercise)


@pytest.mark.parametrize("target", ["timer", "checkpoint"])
@pytest.mark.parametrize("length", [200, 201])
def test_title_length(timer_client: TestClient, target: str, length: int):
    async def exercise():
        async with timer_client.app.state.sql_storage.create_session() as session:
            title = "я" * length
            timer = make_timer(title=title if target == "timer" else "Release sprint")
            if target == "checkpoint":
                timer.checkpoints = [TimerCheckpoint(title=title, time=timer.start_time)]
            session.add(timer)
            if length == 201:
                with pytest.raises(DBAPIError) as error:
                    await session.flush()
                assert getattr(error.value.orig, "sqlstate", None) == "22001"
                await session.rollback()
            else:
                await session.commit()
                if target == "timer":
                    await session.refresh(timer)
                    assert timer.title == title
                else:
                    await session.refresh(timer, ["checkpoints"])
                    assert timer.checkpoints[0].title == title

    assert timer_client.portal is not None
    timer_client.portal.call(exercise)


@pytest.mark.parametrize("violation", ["time_range", "duplicate_participant", "second_creator"])
def test_timer_constraints(timer_client: TestClient, violation: str):
    async def exercise():
        async with timer_client.app.state.sql_storage.create_session() as session:
            timer = make_timer()
            if violation == "time_range":
                timer.end_time = timer.start_time
            elif violation == "duplicate_participant":
                timer.participants = [
                    TimerParticipant(user_id="same-user", user_type=TimerUserType.PARTICIPANT),
                    TimerParticipant(user_id="same-user", user_type=TimerUserType.PARTICIPANT),
                ]
            else:
                timer.participants = [
                    TimerParticipant(user_id="first", user_type=TimerUserType.CREATOR),
                    TimerParticipant(user_id="second", user_type=TimerUserType.CREATOR),
                ]
            session.add(timer)
            with pytest.raises(IntegrityError) as error:
                await session.flush()
            assert getattr(error.value.orig, "sqlstate", None) == ("23514" if violation == "time_range" else "23505")
            await session.rollback()

    assert timer_client.portal is not None
    timer_client.portal.call(exercise)
