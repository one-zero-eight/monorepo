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

migration = import_module("src.schedule_assistant.alembic.versions._2026_09_03_09_00_remove_student_group_kind")


@pytest.fixture
def migration_engine() -> Iterator[Engine]:
    database_name = f"schedule-assistant-migration-{uuid4().hex}"
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


def test_upgrade_removes_kind_from_rows_and_history(
    migration_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = {
        "students_groups": [
            {"code": "AWA-I-1", "kind": "english", "students": []},
            {"code": "G1", "kind": "core", "students": []},
        ]
    }
    patch = [
        {"op": "replace", "path": "/students_groups/0/kind", "value": "english"},
        {
            "op": "add",
            "path": "/students_groups/1",
            "value": {"code": "G1", "kind": "core", "students": []},
        },
        {
            "op": "replace",
            "path": "/students_groups",
            "value": [{"code": "AWA-I-1", "kind": "english", "students": []}],
        },
    ]

    with migration_engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                CREATE TABLE student_groups (
                    code varchar PRIMARY KEY,
                    kind varchar NOT NULL,
                    name varchar,
                    estimated_size integer,
                    students json NOT NULL
                );
                CREATE TABLE config_history_events (
                    id varchar PRIMARY KEY,
                    snapshot json NOT NULL,
                    patch json NOT NULL
                );
                """
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO student_groups (code, kind, students) "
                "VALUES ('AWA-I-1', 'english', '[]'), ('G1', 'core', '[]')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO config_history_events (id, snapshot, patch) "
                "VALUES ('event', CAST(:snapshot AS json), CAST(:patch AS json))"
            ),
            {"snapshot": json.dumps(snapshot), "patch": json.dumps(patch)},
        )

        _run_migration(connection, monkeypatch, "upgrade")

        assert [column["name"] for column in sa.inspect(connection).get_columns("student_groups")] == [
            "code",
            "name",
            "estimated_size",
            "students",
        ]
        event = (
            connection.execute(sa.text("SELECT snapshot, patch FROM config_history_events WHERE id = 'event'"))
            .mappings()
            .one()
        )
        assert event["snapshot"]["students_groups"] == [
            {"code": "AWA-I-1", "students": []},
            {"code": "G1", "students": []},
        ]
        assert event["patch"] == [
            {
                "op": "add",
                "path": "/students_groups/1",
                "value": {"code": "G1", "students": []},
            },
            {
                "op": "replace",
                "path": "/students_groups",
                "value": [{"code": "AWA-I-1", "students": []}],
            },
        ]
