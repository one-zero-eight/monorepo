"""Settings-aware entry points for stock Beanie and Alembic migrations."""

import asyncio
from pathlib import Path

from beanie.migrations.database import DBHandler
from beanie.migrations.models import RunningDirections, RunningMode
from beanie.migrations.runner import MigrationNode
from pymongo import AsyncMongoClient

from src.config_root_schema import load_root_settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MONGO_SERVICES = ("board_games", "clubs", "events", "forms", "guard", "tabletennis", "when2meet")
SQL_SERVICES = ("schedule", "schedule_assistant")
SERVICES = (*MONGO_SERVICES, *SQL_SERVICES)


class MigrationConfigurationError(ValueError):
    """The selected service has no configured migration target."""


def mongo_migration_path(service_name: str) -> Path:
    """Return the service's migration directory independently of the working directory."""
    if service_name not in MONGO_SERVICES:
        raise MigrationConfigurationError(f"Unsupported MongoDB service: {service_name}")
    return REPOSITORY_ROOT / "src" / service_name / "migrations"


async def migrate_mongo(
    service_name: str,
    mongo_uri: str,
    default_database_name: str,
    *,
    migration_path: Path | None = None,
) -> None:
    """Apply pending stock Beanie migrations, closing the client even on failure.

    The URI database takes precedence over ``default_database_name``. Relative
    migration paths are resolved from the repository root, not the process cwd.
    Like Beanie's runner, this entry point must not run concurrently in one process.
    """
    path = mongo_migration_path(service_name)
    if migration_path is not None:
        path = migration_path
    path = (REPOSITORY_ROOT / path).resolve()
    if not path.is_dir():
        raise MigrationConfigurationError(f"Migration directory does not exist for {service_name}")

    client = AsyncMongoClient(mongo_uri)
    try:
        DBHandler.database = client.get_default_database(default=default_database_name)
        DBHandler.client = client
        root = await MigrationNode.build(path)
        await root.run(
            mode=RunningMode(direction=RunningDirections.FORWARD, distance=0),
            allow_index_dropping=False,
            use_transaction=True,
        )
    finally:
        await client.close()


def migrate_service(service_name: str) -> None:
    """Load SETTINGS_PATH and migrate one configured database service to its head."""
    if service_name not in SERVICES:
        raise MigrationConfigurationError(f"Unsupported migration service: {service_name}")

    settings = load_root_settings()
    service_settings = getattr(settings, f"{service_name}_service")
    if service_settings is None:
        raise MigrationConfigurationError(f"Service {service_name} is not configured")

    if service_name in MONGO_SERVICES:
        default_database_name = service_settings.service_name if service_name == "when2meet" else service_name
        asyncio.run(migrate_mongo(service_name, service_settings.mongo.uri.get_secret_value(), default_database_name))
        return

    from alembic import command
    from alembic.config import Config

    config_path = REPOSITORY_ROOT / "src" / service_name / "alembic.ini"
    if not config_path.is_file() or not (config_path.parent / "alembic").is_dir():
        raise MigrationConfigurationError(
            f"Alembic configuration or migration directory does not exist for {service_name}"
        )
    config = Config(str(config_path))
    config.attributes["sqlalchemy.url"] = service_settings.db_url.get_secret_value()
    command.upgrade(config, "head")
