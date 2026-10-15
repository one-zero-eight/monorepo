import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, column, inspect, select, table, text
from sqlalchemy.ext.asyncio import create_async_engine

from src.schedule.models import Base

ALEMBIC_CONFIG = Path(__file__).parents[2] / "src/schedule/alembic.ini"


def ownership_revision():
    revision = ScriptDirectory.from_config(Config(ALEMBIC_CONFIG)).get_revision("f3b9a7c2e614")
    assert revision is not None
    return revision


OWNERSHIP_TABLES = {"event_groups_x_ownerships", "events_x_ownerships", "tags_x_ownerships"}


@pytest.mark.parametrize("populated", [False, True])
def test_drop_ownerships_preserves_unrelated_data(migration_database_url: str, populated: bool):
    config = Config(ALEMBIC_CONFIG)
    migration = ownership_revision()
    engine = create_async_engine(migration_database_url)

    def upgrade(connection: Connection, revision: str):
        config.attributes["connection"] = connection
        command.upgrade(config, revision)

    def snapshot(connection: Connection):
        return {table.name: connection.execute(select(table)).all() for table in Base.metadata.sorted_tables}

    async def check():
        async with engine.begin() as connection:
            await connection.run_sync(upgrade, migration.down_revision)
            before_tables = set(await connection.run_sync(lambda conn: inspect(conn).get_table_names()))
            assert OWNERSHIP_TABLES <= before_tables
            if populated:
                statements = [
                    "INSERT INTO users (id, email, name) VALUES (101001, 'owner@test.example', 'Owner')",
                    (
                        "INSERT INTO event_groups (id, alias, name, description, path) "
                        "VALUES (1, 'preserved-group', 'Group', 'Keep description', 'preserved.ics')"
                    ),
                    (
                        "INSERT INTO tags (id, alias, type, name, satellite) "
                        "VALUES (1, 'preserved-tag', 'course', 'Tag', '{\"keep\": true}')"
                    ),
                    "INSERT INTO events (id, name, description) VALUES (1, 'Event', 'Keep event')",
                    "INSERT INTO event_groups_x_tags (object_id, tag_id) VALUES (1, 1)",
                    "INSERT INTO events_x_event_groups (event_id, event_group_id) VALUES (1, 1)",
                    "INSERT INTO users_x_favorite_groups (user_id, group_alias) VALUES (101001, 'preserved-group')",
                    "INSERT INTO users_x_hidden_groups (user_id, group_alias) VALUES (101001, 'preserved-group')",
                    (
                        "INSERT INTO linked_calendars (id, user_id, alias, url, is_active, name) "
                        "VALUES (1, 101001, 'linked', 'https://calendar.test/all.ics', true, 'Linked')"
                    ),
                    (
                        "INSERT INTO user_schedule_keys (id, user_id, access_key, resource_path) "
                        "VALUES (1, 101001, 'keep-key', '/users/101001/all.ics')"
                    ),
                ]
                for statement in statements:
                    await connection.execute(text(statement))
                for table_name in sorted(OWNERSHIP_TABLES):
                    await connection.execute(
                        table(table_name, column("object_id"), column("user_id"), column("role_alias"))
                        .insert()
                        .values(object_id=1, user_id=101001, role_alias="owner")
                    )
            before_data = await connection.run_sync(snapshot)

        async with engine.begin() as connection:
            await connection.run_sync(upgrade, "head")

        async with engine.begin() as connection:
            after_tables = set(await connection.run_sync(lambda conn: inspect(conn).get_table_names()))
            assert after_tables == before_tables - OWNERSHIP_TABLES
            assert await connection.run_sync(snapshot) == before_data
            assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == migration.revision

            # Re-running the operations after a successful upgrade must be harmless.
            def rerun(conn: Connection):
                with Operations.context(MigrationContext.configure(conn)):
                    migration.module.upgrade()

            await connection.run_sync(rerun)
            assert await connection.run_sync(snapshot) == before_data

    async def run():
        try:
            await check()
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_drop_ownerships_refuses_lossy_downgrade():
    with pytest.raises(RuntimeError, match="restore a database backup"):
        ownership_revision().module.downgrade()
