import json
from collections.abc import Iterator
from importlib import import_module
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Engine

from tests.conftest_runtime_settings import SUITE_POSTGRES_NETLOC

migration = import_module("src.schedule_assistant.alembic.versions._2026_09_04_20_00_course_color")


@pytest.fixture
def migration_engine() -> Iterator[Engine]:
    database_name = f"sa-color-migration-{uuid4().hex}"
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


def _run_migration(connection: sa.Connection, monkeypatch: pytest.MonkeyPatch, direction: str) -> None:
    operations = Operations(MigrationContext.configure(connection))
    monkeypatch.setattr(migration, "op", operations)
    getattr(migration, direction)()


def test_upgrade_adds_color_and_downgrade_cleans_history(
    migration_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = {"courses": [{"name": "Algorithms", "color": "#AABBCC", "components": []}]}
    patch = [
        {"op": "add", "path": "/courses/0/color", "value": "#AABBCC"},
        {
            "op": "replace",
            "path": "/courses/0",
            "value": {"name": "Algorithms", "color": "#AABBCC", "components": []},
        },
        {
            "op": "replace",
            "path": "/courses",
            "value": [{"name": "Algorithms", "color": "#AABBCC", "components": []}],
        },
    ]

    with migration_engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                CREATE TABLE courses (
                    name varchar PRIMARY KEY
                );
                CREATE TABLE config_history_events (
                    id varchar PRIMARY KEY,
                    snapshot json NOT NULL,
                    patch json NOT NULL
                );
                """
            )
        )
        connection.execute(sa.text("INSERT INTO courses (name) VALUES ('Algorithms')"))
        connection.execute(
            sa.text(
                "INSERT INTO config_history_events (id, snapshot, patch) "
                "VALUES ('event', CAST(:snapshot AS json), CAST(:patch AS json))"
            ),
            {"snapshot": json.dumps(snapshot), "patch": json.dumps(patch)},
        )

        _run_migration(connection, monkeypatch, "upgrade")
        color_column = next(
            column for column in sa.inspect(connection).get_columns("courses") if column["name"] == "color"
        )
        assert str(color_column["type"]) == "VARCHAR(7)"
        assert color_column["nullable"] is True

        _run_migration(connection, monkeypatch, "downgrade")
        assert [column["name"] for column in sa.inspect(connection).get_columns("courses")] == ["name"]
        event = (
            connection.execute(sa.text("SELECT snapshot, patch FROM config_history_events WHERE id = 'event'"))
            .mappings()
            .one()
        )
        assert event["snapshot"] == {"courses": [{"name": "Algorithms", "components": []}]}
        assert event["patch"] == [
            {
                "op": "replace",
                "path": "/courses/0",
                "value": {"name": "Algorithms", "components": []},
            },
            {
                "op": "replace",
                "path": "/courses",
                "value": [{"name": "Algorithms", "components": []}],
            },
        ]
