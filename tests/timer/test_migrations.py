import datetime as dtm
import json
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import Connection, inspect, text
from sqlalchemy.dialects.postgresql.base import PGInspector


@pytest.mark.parametrize("populated", [False, True])
def test_upgrade_timer_storage(timer_client: TestClient, populated: bool):
    timestamp = dtm.datetime(2026, 10, 17, 9, tzinfo=dtm.UTC)
    checkpoints = [{"title": "Demo", "time": "2026-10-18T08:00:00Z"}]
    invitation_uuid = uuid4()

    def migrate(connection: Connection):
        config = Config(Path(__file__).parents[2] / "src/timer/alembic.ini")
        config.attributes["connection"] = connection
        revisions = list(ScriptDirectory.from_config(config).walk_revisions())
        assert len(revisions) == 1
        assert revisions[0].down_revision is None
        command.upgrade(config, "head")

        if populated:
            connection.execute(
                text("""
                    INSERT INTO timers (title, start_time, end_time, created_at, updated_at)
                    VALUES ('Hackathon', :timestamp, CAST(:timestamp AS timestamptz) + interval '1 day',
                            :timestamp, :timestamp),
                           ('No checkpoints', :timestamp, CAST(:timestamp AS timestamptz) + interval '1 day',
                            :timestamp, :timestamp)
                """),
                {"timestamp": timestamp},
            )
            connection.execute(
                text("UPDATE timers SET checkpoints = CAST(:checkpoints AS jsonb) WHERE id = 1"),
                {"checkpoints": json.dumps(checkpoints)},
            )
            connection.execute(
                text("""
                    INSERT INTO timer_participants (timer_id, user_id, joined_at, permissions, user_type)
                    VALUES (1, 'creator', :timestamp, ARRAY['update', 'delete', 'invite']::timer_permission[], 'creator')
                """),
                {"timestamp": timestamp},
            )
            connection.execute(
                text("INSERT INTO invitations (uuid, timer_id) VALUES (:uuid, 1)"),
                {"uuid": invitation_uuid},
            )

        first_result = connection.execute(text("SELECT * FROM timers ORDER BY id")).mappings().all()
        first_participants = connection.execute(text("SELECT * FROM timer_participants")).mappings().all()
        first_invitations = connection.execute(text("SELECT * FROM invitations")).mappings().all()
        command.upgrade(config, "head")
        assert connection.execute(text("SELECT * FROM timers ORDER BY id")).mappings().all() == first_result
        assert connection.execute(text("SELECT * FROM timer_participants")).mappings().all() == first_participants
        assert connection.execute(text("SELECT * FROM invitations")).mappings().all() == first_invitations
        assert not inspect(connection).has_table("timer_checkpoints")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "a91d6f2c830b"
        inspector = cast(PGInspector, inspect(connection))
        assert inspector.has_table("invitations")
        assert inspector.get_pk_constraint("invitations")["constrained_columns"] == ["uuid"]
        assert any(index["column_names"] == ["timer_id"] for index in inspector.get_indexes("invitations"))
        schema = connection.scalar(text("SELECT current_schema()"))
        permissions = next(enum for enum in inspector.get_enums(schema=schema) if enum["name"] == "timer_permission")
        assert permissions["labels"] == ["update", "delete", "invite"]

        if populated:
            timer, empty_timer = first_result
            assert timer["id"] == 1
            assert timer["title"] == "Hackathon"
            assert timer["start_time"] == timer["created_at"] == timer["updated_at"] == timestamp
            assert timer["end_time"] == timestamp + dtm.timedelta(days=1)
            assert timer["checkpoints"] == checkpoints
            assert empty_timer["checkpoints"] == []
            participant = connection.execute(text("SELECT * FROM timer_participants")).mappings().one()
            assert participant["user_id"] == "creator"
            assert participant["timer_id"] == 1
            assert participant["joined_at"] == timestamp
            assert participant["permissions"] == ["update", "delete", "invite"]
            assert participant["user_type"] == "creator"
            assert first_invitations == [{"uuid": invitation_uuid, "timer_id": 1}]
        else:
            assert first_result == []

        assert (
            connection.scalar(
                text("""
                INSERT INTO timers (title, start_time, end_time)
                VALUES ('New', :timestamp, CAST(:timestamp AS timestamptz) + interval '1 day')
                RETURNING checkpoints
            """),
                {"timestamp": timestamp},
            )
            == []
        )

    async def exercise():
        async with timer_client.app.state.sql_storage.engine.connect() as connection:
            transaction = await connection.begin()
            try:
                schema = f"timer_migration_{uuid4().hex}"
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await connection.run_sync(migrate)
            finally:
                # Roll back the isolated schema and its data; leave the shared test database intact.
                await transaction.rollback()

    assert timer_client.portal is not None
    timer_client.portal.call(exercise)
