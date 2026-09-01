from collections.abc import Iterator
from importlib import import_module
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Engine

from tests.conftest_runtime_settings import SUITE_POSTGRES_NETLOC

migration = import_module("src.schedule.alembic.versions._2026_09_01_00_00_event_group_alias_preferences")


@pytest.fixture
def migration_engine() -> Iterator[Engine]:
    database_name = f"schedule-migration-{uuid4().hex}"
    admin_engine = sa.create_engine(
        f"postgresql+psycopg://postgres:test@{SUITE_POSTGRES_NETLOC}/postgres",
        isolation_level="AUTOCOMMIT",
    )
    with admin_engine.connect() as connection:
        connection.execute(sa.text(f'CREATE DATABASE "{database_name}"'))

    engine = sa.create_engine(f"postgresql+psycopg://postgres:test@{SUITE_POSTGRES_NETLOC}/{database_name}")
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(sa.text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
        admin_engine.dispose()


def _create_pre_migration_schema(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            """
            CREATE TABLE users (
                id integer PRIMARY KEY
            );
            CREATE TABLE event_groups (
                id integer PRIMARY KEY,
                alias varchar(255) NOT NULL UNIQUE
            );
            CREATE TABLE users_x_favorite_groups (
                user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                group_id integer NOT NULL REFERENCES event_groups(id) ON DELETE CASCADE,
                CONSTRAINT users_x_favorite_groups_pkey PRIMARY KEY (user_id, group_id)
            );
            CREATE TABLE users_x_hidden_groups (
                user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                group_id integer NOT NULL REFERENCES event_groups(id) ON DELETE CASCADE,
                CONSTRAINT users_x_hidden_groups_pkey PRIMARY KEY (user_id, group_id)
            );
            """
        )
    )


def _run_migration(connection: sa.Connection, monkeypatch: pytest.MonkeyPatch, direction: str) -> None:
    operations = Operations(MigrationContext.configure(connection))
    monkeypatch.setattr(migration, "op", operations)
    getattr(migration, direction)()


def test_upgrade_and_downgrade_preserve_preferences(
    migration_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with migration_engine.begin() as connection:
        _create_pre_migration_schema(connection)
        connection.execute(sa.text("INSERT INTO users (id) VALUES (1), (2)"))
        connection.execute(sa.text("INSERT INTO event_groups (id, alias) VALUES (10, 'core-a'), (20, 'elective-b')"))
        connection.execute(
            sa.text("INSERT INTO users_x_favorite_groups (user_id, group_id) VALUES (1, 10), (1, 20), (2, 20)")
        )
        connection.execute(sa.text("INSERT INTO users_x_hidden_groups (user_id, group_id) VALUES (1, 20), (2, 20)"))

        _run_migration(connection, monkeypatch, "upgrade")

        favorites = connection.execute(
            sa.text("SELECT user_id, group_alias FROM users_x_favorite_groups ORDER BY user_id, group_alias")
        ).all()
        hidden = connection.execute(
            sa.text("SELECT user_id, group_alias FROM users_x_hidden_groups ORDER BY user_id, group_alias")
        ).all()
        assert favorites == [(1, "core-a"), (1, "elective-b"), (2, "elective-b")]
        assert hidden == [(1, "elective-b"), (2, "elective-b")]

        _run_migration(connection, monkeypatch, "downgrade")

        favorites = connection.execute(
            sa.text("SELECT user_id, group_id FROM users_x_favorite_groups ORDER BY user_id, group_id")
        ).all()
        hidden = connection.execute(
            sa.text("SELECT user_id, group_id FROM users_x_hidden_groups ORDER BY user_id, group_id")
        ).all()
        assert favorites == [(1, 10), (1, 20), (2, 20)]
        assert hidden == [(1, 20), (2, 20)]


def test_upgrade_aborts_on_unmapped_group_id(
    migration_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with migration_engine.begin() as connection:
        _create_pre_migration_schema(connection)
        connection.execute(sa.text("INSERT INTO users (id) VALUES (1)"))
        connection.execute(sa.text("SET session_replication_role = replica"))
        connection.execute(sa.text("INSERT INTO users_x_favorite_groups (user_id, group_id) VALUES (1, 999)"))
        connection.execute(sa.text("SET session_replication_role = origin"))

    with (
        pytest.raises(RuntimeError, match="rows have no event group alias"),
        migration_engine.begin() as connection,
    ):
        _run_migration(connection, monkeypatch, "upgrade")

    with migration_engine.connect() as connection:
        columns = sa.inspect(connection).get_columns("users_x_favorite_groups")
        assert [column["name"] for column in columns] == ["user_id", "group_id"]
        assert connection.scalar(sa.text("SELECT count(*) FROM users_x_favorite_groups")) == 1


def test_downgrade_aborts_without_deleting_unmapped_alias(
    migration_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with migration_engine.begin() as connection:
        _create_pre_migration_schema(connection)
        connection.execute(sa.text("INSERT INTO users (id) VALUES (1)"))
        connection.execute(sa.text("INSERT INTO event_groups (id, alias) VALUES (10, 'local-group')"))
        connection.execute(sa.text("INSERT INTO users_x_favorite_groups (user_id, group_id) VALUES (1, 10)"))
        _run_migration(connection, monkeypatch, "upgrade")
        connection.execute(
            sa.text("INSERT INTO users_x_favorite_groups (user_id, group_alias) VALUES (1, 'virtual-group')")
        )

    with (
        pytest.raises(RuntimeError, match="aliases do not map to local event groups"),
        migration_engine.begin() as connection,
    ):
        _run_migration(connection, monkeypatch, "downgrade")

    with migration_engine.connect() as connection:
        columns = sa.inspect(connection).get_columns("users_x_favorite_groups")
        assert [column["name"] for column in columns] == ["user_id", "group_alias"]
        aliases = connection.scalars(
            sa.text("SELECT group_alias FROM users_x_favorite_groups ORDER BY group_alias")
        ).all()
        assert aliases == ["local-group", "virtual-group"]
