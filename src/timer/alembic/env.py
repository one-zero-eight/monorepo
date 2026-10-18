import asyncio

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from src.config_root_schema import load_root_settings, require_not_none
from src.timer.db.models import Base

config = context.config
target_metadata = Base.metadata


def database_url() -> str:
    url = config.attributes.get("sqlalchemy.url")
    if url is not None:
        return url
    settings = require_not_none(load_root_settings().timer_service, "Timer settings are not configured")
    return settings.db_url.get_secret_value()


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_server_default=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(database_url(), poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif (connection := config.attributes.get("connection")) is not None:
    run_migrations(connection)
else:
    asyncio.run(run_async_migrations())
