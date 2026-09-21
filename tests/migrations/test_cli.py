import asyncio
import os
import shutil
import subprocess  # noqa: S404 — exercise the public CLI in an isolated interpreter.
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import pytest
import sqlalchemy as sa
import yaml
from alembic.config import Config
from alembic.script import ScriptDirectory
from pymongo import MongoClient
from pymongo.database import Database

from src.migrations import (
    MONGO_SERVICES,
    REPOSITORY_ROOT,
    SERVICES,
    SQL_SERVICES,
    MigrationConfigurationError,
    migrate_mongo,
    mongo_migration_path,
)
from tests.conftest_runtime_settings import (
    SUITE_MONGO_AUTH,
    SUITE_MONGO_NETLOC,
    SUITE_MONGO_USER,
    SUITE_POSTGRES_NETLOC,
)

TRANSACTIONAL_MIGRATIONS = Path(__file__).parent / "fixtures" / "transactional"
MIGRATION_NAME = "20260911000000_mark_records.py"


def mongo_uri(database_name: str = "") -> str:
    user = quote(SUITE_MONGO_USER, safe="")
    password = quote(SUITE_MONGO_AUTH, safe="")
    return (
        f"mongodb://{user}:{password}@{SUITE_MONGO_NETLOC}/{database_name}"
        "?authSource=admin&replicaSet=rs0&directConnection=true&serverSelectionTimeoutMS=3000"
    )


@pytest.fixture
def mongo_databases() -> Iterator[tuple[Database, Database]]:
    with MongoClient(mongo_uri()) as client:
        databases = (
            client[f"migrations-target-{uuid4().hex}"],
            client[f"migrations-other-{uuid4().hex}"],
        )
        try:
            yield databases
        finally:
            for database in databases:
                client.drop_database(database.name)


def write_settings(path: Path, services: dict[str, dict[str, Any]]) -> Path:
    settings = {
        "accounts": {"api_url": "http://127.0.0.1:1/accounts", "api_jwt_token": "cli-secret-must-stay-private"},
        **{f"{name}_service": values for name, values in services.items()},
    }
    path.write_text(yaml.safe_dump(settings), encoding="utf-8")
    return path


def service_settings(service_name: str, uri: str) -> dict[str, Any]:
    settings: dict[str, Any] = {"mongo": {"uri": uri}}
    if service_name in ("board_games", "clubs", "events"):
        settings["minio"] = {"endpoint": "127.0.0.1:1"}
    if service_name == "events":
        settings["clubs"] = {"api_url": "http://127.0.0.1:1/clubs", "api_key": "unused-test-key"}
    if service_name == "forms":
        settings["links"] = {"signature_secret": "unused-test-secret"}
    if service_name == "guard":
        settings["google"] = {"service_account_file_path": "/nonexistent/migration-test-credentials.json"}
    return settings


@pytest.fixture
def repository_with_test_migration(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    shutil.copytree(REPOSITORY_ROOT / "src", repository / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(TRANSACTIONAL_MIGRATIONS, repository / "src/when2meet/migrations", dirs_exist_ok=True)
    return repository


def run_cli(
    service_name: str, settings_path: Path, cwd: Path, *, repository: Path = REPOSITORY_ROOT
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "SETTINGS_PATH": str(settings_path),
        "PYTHONPATH": str(repository),
        # The wrapper must not inherit Beanie CLI overrides, including false/zero options.
        "BEANIE_URI": "not-a-mongo-uri",
        "BEANIE_DB": "wrong-database",
        "BEANIE_DISTANCE": "1",
        "BEANIE_ALLOW_INDEX_DROPPING": "true",
    }
    return subprocess.run(  # noqa: S603 — fixed module and interpreter, service is a test parameter.
        [sys.executable, "-m", "src.migrations", service_name],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=40,
        check=False,
    )


@pytest.mark.parametrize("service_name", SERVICES)
def test_cli_rejects_unconfigured_service(service_name: str, tmp_path: Path) -> None:
    settings_path = write_settings(tmp_path / "settings.yaml", {})
    result = run_cli(service_name, settings_path, tmp_path)
    assert result.returncode != 0
    assert f"Service {service_name} is not configured" in result.stderr
    assert "Traceback" not in result.stderr
    assert "cli-secret-must-stay-private" not in result.stdout + result.stderr


@pytest.mark.parametrize("service_name", ["not-a-service", "maps", "room_booking", "student_affairs"])
def test_cli_rejects_invalid_or_database_free_service(service_name: str, tmp_path: Path) -> None:
    result = run_cli(service_name, tmp_path / "missing.yaml", tmp_path)
    assert result.returncode != 0
    assert "invalid choice" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_fails_for_missing_settings(tmp_path: Path) -> None:
    result = run_cli("tabletennis", tmp_path / "missing.yaml", tmp_path)
    assert result.returncode != 0
    assert "FileNotFoundError" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_does_not_expose_invalid_mongo_uri(tmp_path: Path) -> None:
    secret = f"connection-value-{uuid4().hex}"
    uri = f"invalid-scheme://test:{secret}@127.0.0.1/unused"
    settings_path = write_settings(tmp_path / "settings.yaml", {"tabletennis": service_settings("tabletennis", uri)})
    result = run_cli("tabletennis", settings_path, tmp_path)
    assert result.returncode != 0
    assert "InvalidURI" in result.stderr
    assert secret not in result.stdout + result.stderr
    assert uri not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_cli_does_not_expose_invalid_configuration(tmp_path: Path) -> None:
    secret = f"configuration-value-{uuid4().hex}"
    settings_path = write_settings(tmp_path / "settings.yaml", {"tabletennis": {"mongo": secret}})
    result = run_cli("tabletennis", settings_path, tmp_path)
    assert result.returncode != 0
    assert "ValidationError" in result.stderr
    assert secret not in result.stdout + result.stderr


@pytest.mark.parametrize("service_name", MONGO_SERVICES)
def test_cli_runs_only_configured_mongo_service(
    service_name: str, mongo_databases: tuple[Database, Database], tmp_path: Path
) -> None:
    target, other = mongo_databases
    uri = mongo_uri(target.name)
    settings_path = write_settings(
        tmp_path / "selected-settings.yaml",
        {service_name: service_settings(service_name, uri)},
    )
    # A conflicting cwd settings file must not replace SETTINGS_PATH.
    write_settings(tmp_path / "settings.yaml", {})
    result = run_cli(service_name, settings_path, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Migrations completed for {service_name}." in result.stdout
    assert uri not in result.stdout + result.stderr
    assert "cli-secret-must-stay-private" not in result.stdout + result.stderr
    assert other.list_collection_names() == []
    assert target.list_collection_names() == []


@pytest.mark.parametrize("uri_has_database", [True, False])
def test_runner_honors_uri_database_before_default(
    uri_has_database: bool,
    mongo_databases: tuple[Database, Database],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target, other = mongo_databases
    for database in (target, other):
        database.records.insert_one({"_id": "record"})
    uri = mongo_uri(target.name if uri_has_database else "")
    default_database = other if uri_has_database else target
    monkeypatch.chdir(tmp_path)
    asyncio.run(
        migrate_mongo(
            "tabletennis",
            uri,
            default_database.name,
            migration_path=TRANSACTIONAL_MIGRATIONS.relative_to(REPOSITORY_ROOT),
        )
    )
    target_record = target.records.find_one({"_id": "record"})
    other_record = other.records.find_one({"_id": "record"})
    assert target_record is not None
    assert other_record is not None
    assert target_record["migration_count"] == 1
    assert "migrated" not in other_record
    assert other.migrations_log.count_documents({}) == 0


def test_stock_runner_rolls_back_and_replays_after_history_gap(
    mongo_databases: tuple[Database, Database],
) -> None:
    target, _ = mongo_databases
    target.records.insert_many([{"_id": "good"}, {"_id": "bad", "fail_migration": True}])
    target.records.create_index("keep_me", name="existing_index")

    def run() -> None:
        asyncio.run(
            migrate_mongo("tabletennis", mongo_uri(target.name), target.name, migration_path=TRANSACTIONAL_MIGRATIONS)
        )

    with pytest.raises(RuntimeError, match="Deliberate failure after writing records"):
        run()
    assert target.records.count_documents({"migrated": {"$exists": True}}) == 0
    assert target.migrations_log.count_documents({}) == 0
    assert "existing_index" in target.records.index_information()

    target.records.update_one({"_id": "bad"}, {"$unset": {"fail_migration": ""}})
    run()
    run()
    assert target.records.count_documents({"migrated": True, "migration_count": 1}) == 2
    assert target.migrations_log.count_documents({"name": MIGRATION_NAME, "is_current": True}) == 1
    assert target.migrations_log.count_documents({}) == 1

    # Beanie commits data before writing its history. Emulate that gap without
    # altering the runner: an idempotent historical migration must replay safely.
    target.migrations_log.delete_many({})
    run()
    assert target.records.count_documents({"migrated": True, "migration_count": 1}) == 2
    assert target.migrations_log.count_documents({"name": MIGRATION_NAME, "is_current": True}) == 1
    assert "existing_index" in target.records.index_information()


def test_empty_directory_is_valid_without_fake_history(
    mongo_databases: tuple[Database, Database], tmp_path: Path
) -> None:
    target, _ = mongo_databases
    asyncio.run(migrate_mongo("tabletennis", mongo_uri(target.name), target.name, migration_path=tmp_path))
    assert target.list_collection_names() == []


def test_missing_directory_fails_before_connecting(tmp_path: Path) -> None:
    with pytest.raises(MigrationConfigurationError, match="Migration directory does not exist"):
        asyncio.run(migrate_mongo("tabletennis", "not-a-uri", "unused", migration_path=tmp_path / "typo"))


def test_runner_rejects_invalid_service_before_connecting(tmp_path: Path) -> None:
    with pytest.raises(MigrationConfigurationError, match="Unsupported MongoDB service"):
        asyncio.run(migrate_mongo("maps", "not-a-uri", "unused", migration_path=tmp_path))


@pytest.mark.parametrize("service_name", MONGO_SERVICES)
def test_service_directories_exist_independently_of_cwd(
    service_name: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    assert mongo_migration_path(service_name).is_absolute()
    assert mongo_migration_path(service_name).is_dir()


@pytest.mark.parametrize("uri_has_database", [True, False])
def test_cli_honors_when2meet_configured_database_name(
    uri_has_database: bool,
    mongo_databases: tuple[Database, Database],
    tmp_path: Path,
    repository_with_test_migration: Path,
) -> None:
    target, other = mongo_databases
    settings = service_settings("when2meet", mongo_uri(target.name if uri_has_database else ""))
    settings["service_name"] = other.name if uri_has_database else target.name
    settings_path = write_settings(tmp_path / "settings.yaml", {"when2meet": settings})
    result = run_cli("when2meet", settings_path, tmp_path, repository=repository_with_test_migration)
    assert result.returncode == 0, result.stdout + result.stderr
    assert target.migrations_log.count_documents({"is_current": True}) == 1
    assert other.list_collection_names() == []


def test_cli_migration_failure_returns_nonzero_without_sensitive_data(
    mongo_databases: tuple[Database, Database], tmp_path: Path, repository_with_test_migration: Path
) -> None:
    target, _ = mongo_databases
    secret = f"migration-value-{uuid4().hex}"
    target.records.insert_one({"_id": "malformed", "fail_migration": True, "secret": secret})
    uri = mongo_uri(target.name)
    settings_path = write_settings(tmp_path / "settings.yaml", {"when2meet": service_settings("when2meet", uri)})
    result = run_cli("when2meet", settings_path, tmp_path, repository=repository_with_test_migration)
    assert result.returncode != 0
    assert "Migrations failed for when2meet" in result.stderr
    assert "Traceback" not in result.stderr
    assert uri not in result.stdout + result.stderr
    assert secret not in result.stdout + result.stderr
    assert target.migrations_log.count_documents({}) == 0
    record = target.records.find_one({"_id": "malformed"})
    assert record == {"_id": "malformed", "fail_migration": True, "secret": secret}


@pytest.fixture
def sql_database() -> Iterator[str]:
    database_name = f"migrations-sql-{uuid4().hex}"
    admin_engine = sa.create_engine(
        f"postgresql+psycopg://postgres:test@{SUITE_POSTGRES_NETLOC}/postgres",
        isolation_level="AUTOCOMMIT",
    )
    try:
        with admin_engine.connect() as connection:
            connection.execute(sa.text(f'CREATE DATABASE "{database_name}"'))
        try:
            yield database_name
        finally:
            with admin_engine.connect() as connection:
                connection.execute(sa.text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
    finally:
        admin_engine.dispose()


@pytest.mark.parametrize("service_name", SQL_SERVICES)
def test_cli_upgrades_sql_service_to_head(service_name: str, sql_database: str, tmp_path: Path) -> None:
    driver = "asyncpg" if service_name == "schedule" else "psycopg"
    settings: dict[str, Any] = {
        "db_url": f"postgresql+{driver}://postgres:test@{SUITE_POSTGRES_NETLOC}/{sql_database}",
    }
    if service_name == "schedule_assistant":
        settings["api_key"] = "unused-test-key"
        settings["booking"] = {"api_key": "unused-test-key"}
    settings_path = write_settings(tmp_path / "selected-settings.yaml", {service_name: settings})
    write_settings(tmp_path / "settings.yaml", {})
    result = run_cli(service_name, settings_path, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert settings["db_url"] not in result.stdout + result.stderr

    expected_head = ScriptDirectory.from_config(
        Config(str(REPOSITORY_ROOT / "src" / service_name / "alembic.ini"))
    ).get_current_head()
    engine = sa.create_engine(f"postgresql+psycopg://postgres:test@{SUITE_POSTGRES_NETLOC}/{sql_database}")
    try:
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == expected_head
        result = run_cli(service_name, settings_path, tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        engine.dispose()
