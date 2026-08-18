"""Schedule Assistant tests: patched settings without full suite infra."""

import asyncio
from collections.abc import AsyncGenerator, Iterator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest_runtime_settings import (
    SUITE_POSTGRES_NETLOC,
    schedule_assistant_test_database_name,
)


async def _ensure_postgres_database(admin_dsn: str, database_name: str) -> None:
    engine = create_async_engine(admin_dsn, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": database_name},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        await engine.dispose()


def _schedule_assistant_admin_dsn() -> str:
    return f"postgresql+asyncpg://postgres:test@{SUITE_POSTGRES_NETLOC}/postgres"


def schedule_assistant_db_url() -> str:
    return f"postgresql+psycopg://postgres:test@{SUITE_POSTGRES_NETLOC}/{schedule_assistant_test_database_name()}"


def _prepare_schedule_assistant_schema() -> None:
    import src.schedule_assistant.db.models  # noqa: F401
    from src.schedule_assistant.config import settings
    from src.schedule_assistant.db.base import Base
    from src.schedule_assistant.db.session import get_engine

    engine = get_engine(settings.db_url.get_secret_value())
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    engine.dispose()


async def _truncate_schedule_assistant_tables() -> None:
    import src.schedule_assistant.db.models  # noqa: F401
    from src.schedule_assistant.config import settings
    from src.schedule_assistant.db.base import Base
    from src.schedule_assistant.db.session import get_engine

    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    if not table_names:
        return
    engine = get_engine(settings.db_url.get_secret_value())
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
    engine.dispose()


@pytest.fixture(scope="session")
def schedule_assistant_postgres(request: pytest.FixtureRequest) -> Iterator[None]:
    asyncio.run(_ensure_postgres_database(_schedule_assistant_admin_dsn(), schedule_assistant_test_database_name()))
    _prepare_schedule_assistant_schema()
    yield


@pytest.fixture
def schedule_assistant_repo(
    schedule_assistant_postgres: None,
    monkeypatch: pytest.MonkeyPatch,
):
    from src.schedule_assistant.modules.distributions.repository import DistributionUploadRepository
    from src.schedule_assistant.modules.instructor_preferences.repository import PreferenceInviteRepository
    from src.schedule_assistant.modules.schedule_config.repository import ScheduleConfigRepository

    asyncio.run(_truncate_schedule_assistant_tables())
    repo = ScheduleConfigRepository(schedule_assistant_db_url())
    invite_repo = PreferenceInviteRepository(schedule_assistant_db_url())
    distribution_repo = DistributionUploadRepository(schedule_assistant_db_url())
    monkeypatch.setattr(
        "src.schedule_assistant.modules.schedule_config.repository.schedule_config_repository",
        repo,
    )
    monkeypatch.setattr(
        "src.schedule_assistant.modules.instructor_preferences.repository.preference_invite_repository",
        invite_repo,
    )
    monkeypatch.setattr(
        "src.schedule_assistant.modules.instructor_preferences.routes.preference_invite_repository",
        invite_repo,
    )
    monkeypatch.setattr(
        "src.schedule_assistant.modules.distributions.repository.distribution_upload_repository",
        distribution_repo,
    )
    monkeypatch.setattr(
        "src.schedule_assistant.modules.distributions.routes.distribution_upload_repository",
        distribution_repo,
    )
    return repo


@pytest.fixture
def schedule_config_repo(schedule_assistant_repo, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "src.schedule_assistant.modules.schedule_config.routes.schedule_config_repository",
        schedule_assistant_repo,
    )
    return schedule_assistant_repo


@pytest.fixture
def schedule_data_repo(schedule_assistant_repo, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "src.schedule_assistant.modules.schedule.service.schedule_config_repository",
        schedule_assistant_repo,
    )
    return schedule_assistant_repo


@pytest.fixture
def issues_repo(schedule_assistant_repo, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "src.schedule_assistant.modules.issues.service.schedule_config_repository",
        schedule_assistant_repo,
    )
    return schedule_assistant_repo


@pytest.fixture
def bookings_repo(schedule_assistant_repo, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "src.schedule_assistant.modules.bookings.service.schedule_config_repository",
        schedule_assistant_repo,
    )
    return schedule_assistant_repo


@pytest.fixture(scope="session")
def schedule_assistant_client(request: pytest.FixtureRequest) -> Iterator[TestClient]:
    request.getfixturevalue("mock_inh_accounts_http")
    request.getfixturevalue("schedule_assistant_postgres")
    from src.schedule_assistant.app import app

    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
def fastapi_app() -> FastAPI:
    from src.schedule_assistant.app import app

    return app


@pytest_asyncio.fixture(scope="function")
async def fastapi_test_client(
    fastapi_app: FastAPI,
) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def authenticated_client(fastapi_app: FastAPI) -> AsyncGenerator[AsyncClient]:
    # Import after pytest_configure patches load_root_settings (suite isolation).
    from src.inh_accounts_sdk import UserTokenData
    from src.schedule_assistant.dependencies import verify_token_dep

    async def fake_verify_token_dep() -> tuple[UserTokenData, str]:
        return UserTokenData(innohassle_id="123", email="test@test.com"), "test_token"

    fastapi_app.dependency_overrides[verify_token_dep] = fake_verify_token_dep

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        yield client

    fastapi_app.dependency_overrides.pop(verify_token_dep)


@pytest.fixture(scope="function")
def mock_booking_client():
    from src.schedule_assistant.modules.bookings.client import BookingDTO, CancelAutoBookingsResult, RoomDTO

    mock_client = AsyncMock()

    bookings = [
        {
            "room_id": "test_room_1",
            "event_id": "event_1",
            "title": "Test Booking 1",
            "start": "2025-01-01T09:00:00Z",
            "end": "2025-01-01T10:00:00Z",
        },
        {
            "room_id": "test_room_2",
            "event_id": "event_2",
            "title": "Test Booking 2",
            "start": "2025-01-01T11:00:00Z",
            "end": "2025-01-01T12:00:00Z",
        },
    ]

    mock_client.get_all_bookings.return_value = [BookingDTO.model_validate(booking) for booking in bookings]
    mock_client.get_room_bookings.return_value = [BookingDTO.model_validate(booking) for booking in bookings[:1]]

    mock_client.get_rooms.return_value = [
        RoomDTO(
            id="test_room_1",
            title="Test Room 1",
            short_name="TR1",
            my_uni_id=101,
            capacity=25,
            access_level="yellow",
            restrict_daytime=False,
        ),
        RoomDTO(
            id="test_room_2",
            title="Test Room 2",
            short_name="TR2",
            my_uni_id=102,
            capacity=50,
            access_level="red",
            restrict_daytime=True,
        ),
    ]
    mock_client.get_auto_bookings.return_value = []
    mock_client.cancel_auto_bookings_batch.return_value = CancelAutoBookingsResult(cancelled=[], failed={})
    mock_client.cancel_auto_booking.return_value = None
    mock_client.cancel_extra_booking.return_value = None

    with (
        patch("src.schedule_assistant.modules.bookings.client.booking_client", mock_client),
        patch("src.schedule_assistant.modules.bookings.service.booking_client", mock_client),
    ):
        yield mock_client
