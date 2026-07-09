"""Wait on suite Mongo/MinIO; point ``load_root_settings`` at suite-sized ``Settings``."""

import os
import tempfile
import time as tm
from pathlib import Path

import pytest
import urllib3
from minio import Minio
from minio.error import MinioException
from pydantic import SecretStr
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from urllib3.exceptions import HTTPError

from src.clubs.config_schema import ClubsSettings
from src.common_config import Environment, MinioSettings, MongoDatabaseSettings
from src.config_root_schema import AccountsSettings, Settings
from src.forms.config_schema import FormsSettings, LinksSettings
from src.guard.config_schema import GuardSettings
from src.maps.config_schema import MapsSettings
from src.room_booking.config_schema import BmpExchange, Exchange, RoomBookingSettings
from src.schedule.config_schema import ScheduleSettings
from src.schedule_assistant.config_schema import (
    RoomBookingSettings as ScheduleAssistantRoomBookingSettings,
)
from src.schedule_assistant.config_schema import (
    ScheduleAssistantSettings,
)
from src.student_affairs.config_schema import OmnideskSettings, StudentAffairsSettings
from src.tabletennis.config_schema import TabletennisSettings
from src.when2meet.config_schema import When2MeetSettings

# Host ports for docker-compose.test.yaml and CI service containers; override via SUITE_* env.
SUITE_MONGO_NETLOC = os.environ.get("SUITE_MONGO_NETLOC", "127.0.0.1:37017")
SUITE_MONGO_USER = os.environ.get("SUITE_MONGO_USER", "test")
SUITE_MONGO_AUTH = os.environ.get("SUITE_MONGO_AUTH", "test")
SUITE_MINIO_ENDPOINT = os.environ.get("SUITE_MINIO_ENDPOINT", "127.0.0.1:19000")
SUITE_MINIO_ACCESS_KEY = os.environ.get("SUITE_MINIO_ACCESS_KEY", "test")
SUITE_MINIO_KEY = os.environ.get("SUITE_MINIO_KEY", "testsecret")
SUITE_POSTGRES_NETLOC = os.environ.get("SUITE_POSTGRES_NETLOC", "127.0.0.1:35432")


def is_xdist_worker() -> bool:
    return os.environ.get("PYTEST_XDIST_WORKER") is not None


def get_worker_id() -> str:
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


def schedule_test_database_name() -> str:
    return f"worker-{get_worker_id()}-schedule"


def schedule_test_predefined_dir() -> Path:
    return Path(tempfile.gettempdir()) / f"worker-{get_worker_id()}-schedule-predefined"


def schedule_assistant_test_database_name() -> str:
    return f"worker-{get_worker_id()}-schedule-assistant"


def load_root_settings() -> Settings:
    mongo_uri = f"mongodb://{SUITE_MONGO_USER}:{SUITE_MONGO_AUTH}@{SUITE_MONGO_NETLOC}/worker-{get_worker_id()}-<service_name>?authSource=admin"
    minio_bucket = f"worker-{get_worker_id()}-<service_name>"

    return Settings(
        accounts=AccountsSettings(
            mock=False,
            api_jwt_token=SecretStr("test-token"),
        ),
        maps_service=MapsSettings(
            environment=Environment.TESTING,
        ),
        clubs_service=ClubsSettings(
            environment=Environment.TESTING,
            superadmin_emails=["admin@innopolis.university"],
            mongo=MongoDatabaseSettings(
                uri=SecretStr(mongo_uri.replace("<service_name>", "clubs")),
            ),
            minio=MinioSettings(
                endpoint=SUITE_MINIO_ENDPOINT,
                access_key=SUITE_MINIO_ACCESS_KEY,
                secret_key=SecretStr(SUITE_MINIO_KEY),
                bucket=minio_bucket.replace("<service_name>", "clubs"),
            ),
        ),
        student_affairs_service=StudentAffairsSettings(
            environment=Environment.TESTING,
            omnidesk=OmnideskSettings(jwt_marker=SecretStr("test-marker-0123456789abcdef")),
        ),
        when2meet_service=When2MeetSettings(
            environment=Environment.TESTING,
            app_root_path="/api/v0",
            mongo=MongoDatabaseSettings(
                uri=SecretStr(mongo_uri.replace("<service_name>", "when2meet")),
            ),
        ),
        tabletennis_service=TabletennisSettings(
            environment=Environment.TESTING,
        ),
        guard_service=GuardSettings(
            environment=Environment.TESTING,
            mongo=MongoDatabaseSettings(
                uri=SecretStr(mongo_uri.replace("<service_name>", "guard")),
            ),
        ),
        forms_service=FormsSettings(
            environment=Environment.TESTING,
            mongo=MongoDatabaseSettings(
                uri=SecretStr(mongo_uri.replace("<service_name>", "forms")),
            ),
            links=LinksSettings(signature_secret=SecretStr("test-secret")),
        ),
        room_booking_service=RoomBookingSettings(
            environment=Environment.TESTING,
            api_key=SecretStr("test-room-booking-api-key"),
            exchange=Exchange(
                username="test@innopolis.ru",
                password=SecretStr("test-password"),
                bmp=BmpExchange(
                    username="bmp-test@innopolis.ru",
                    password=SecretStr("bmp-test-password"),
                ),
            ),
        ),
        schedule_service=ScheduleSettings(
            environment=Environment.TESTING,
            app_root_path="/schedule/v0",
            db_url=SecretStr(
                f"postgresql+asyncpg://postgres:test@{SUITE_POSTGRES_NETLOC}/{schedule_test_database_name()}"
            ),
            predefined_dir=schedule_test_predefined_dir(),
        ),
        schedule_assistant_service=ScheduleAssistantSettings(
            environment=Environment.TESTING,
            app_root_path="/schedule-assistant/v0",
            db_url=SecretStr(
                f"postgresql+psycopg://postgres:test@{SUITE_POSTGRES_NETLOC}/{schedule_assistant_test_database_name()}"
            ),
            booking=ScheduleAssistantRoomBookingSettings(api_key=SecretStr("test-room-booking-api-key")),
        ),
    )


def _wait_mongo_ready(uri: str, timeout_s: float = 1) -> None:
    client = MongoClient(uri, serverSelectionTimeoutMS=int(timeout_s * 1000))
    try:
        client.admin.command("ping")
    finally:
        client.close()


def _wait_postgres_ready(dsn: str, timeout_s: float = 1) -> None:
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def ping() -> None:
        engine = create_async_engine(dsn)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()

    asyncio.run(ping())


def _wait_minio_ready(timeout_s: float = 1) -> None:
    http = urllib3.PoolManager(timeout=urllib3.Timeout(connect=timeout_s, read=timeout_s))
    mc = Minio(
        endpoint=SUITE_MINIO_ENDPOINT,
        access_key=SUITE_MINIO_ACCESS_KEY,
        secret_key=SUITE_MINIO_KEY,
        secure=False,
        http_client=http,
    )
    mc.list_buckets()


suite_timings_stash_key: pytest.StashKey[dict[str, float]] = pytest.StashKey()
suite_monkeypatch_stash_key: pytest.StashKey[pytest.MonkeyPatch] = pytest.StashKey()


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    if getattr(config.option, "collectonly", False):
        return

    if not is_xdist_worker():  # Run only on master worker
        timings: dict[str, float] = {}
        config.stash[suite_timings_stash_key] = timings

        t_suite = tm.perf_counter()

        t0 = tm.perf_counter()
        try:
            _wait_minio_ready()
        except (MinioException, HTTPError, OSError) as exc:
            pytest.exit(
                f"MinIO not ready, run it with `docker compose -f docker-compose.test.yaml up --wait` and try again:\n{exc}",
                returncode=1,
            )
        timings["infra.minio_wait_ready_s"] = tm.perf_counter() - t0

        t0 = tm.perf_counter()
        try:
            _wait_mongo_ready(
                f"mongodb://{SUITE_MONGO_USER}:{SUITE_MONGO_AUTH}@{SUITE_MONGO_NETLOC}/admin?authSource=admin"
            )
        except PyMongoError as exc:
            pytest.exit(
                f"MongoDB not ready, run it with `docker compose -f docker-compose.test.yaml up --wait` and try again:\n{exc}",
                returncode=1,
            )
        timings["infra.mongo_wait_ready_s"] = tm.perf_counter() - t0

        t0 = tm.perf_counter()
        from sqlalchemy.exc import SQLAlchemyError

        try:
            _wait_postgres_ready(f"postgresql+asyncpg://postgres:test@{SUITE_POSTGRES_NETLOC}/postgres")
        except (OSError, SQLAlchemyError) as exc:
            pytest.exit(
                f"PostgreSQL not ready, run it with `docker compose -f docker-compose.test.yaml up --wait` and try again:\n{exc}",
                returncode=1,
            )
        timings["infra.postgres_wait_ready_s"] = tm.perf_counter() - t0

        timings["infra.total_start_s"] = tm.perf_counter() - t_suite

    mp = pytest.MonkeyPatch()

    import src.config_root_schema

    mp.setattr(src.config_root_schema, "load_root_settings", load_root_settings)
    config.stash[suite_monkeypatch_stash_key] = mp


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config: pytest.Config) -> None:
    mp = config.stash.get(suite_monkeypatch_stash_key, None)
    if mp is not None:
        mp.undo()
        del config.stash[suite_monkeypatch_stash_key]


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter, exitstatus: int, config: pytest.Config) -> None:
    timings = config.stash.get(suite_timings_stash_key, None)
    if not timings:
        return
    terminalreporter.write_line("")
    terminalreporter.write_line("Infrastructure startup")
    for key in timings:
        terminalreporter.write_line(f"{timings[key]:.3f}s {key}")
