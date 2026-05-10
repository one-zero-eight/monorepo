"""Wait on suite Mongo/MinIO; point ``load_root_settings`` at suite-sized ``Settings``."""

import os
import time

import pytest
from minio import Minio
from pydantic import SecretStr
from pymongo import MongoClient

from src.clubs.config_schema import ClubsSettings
from src.common_config import Environment, MinioSettings, MongoDatabaseSettings
from src.config_root_schema import AccountsSettings, Settings
from src.maps.config_schema import MapsSettings
from src.student_affairs.config_schema import OmnideskSettings, StudentAffairsSettings

# docker-compose.test.yaml (Mongo 37017, MinIO API 19000; MinIO rejects secrets < 8 chars)
SUITE_MONGO_NETLOC = "127.0.0.1:37017"
SUITE_MONGO_USER = "test"
SUITE_MONGO_PASSWORD = "test"
SUITE_MINIO_ENDPOINT = "127.0.0.1:19000"
SUITE_MINIO_ACCESS_KEY = "test"
SUITE_MINIO_SECRET_KEY = "testsecret"


def is_xdist_worker() -> bool:
    return os.environ.get("PYTEST_XDIST_WORKER") is not None


def get_worker_id() -> str:
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


def load_root_settings() -> Settings:
    mongo_uri = f"mongodb://{SUITE_MONGO_USER}:{SUITE_MONGO_PASSWORD}@{SUITE_MONGO_NETLOC}/worker-{get_worker_id()}-<service_name>?authSource=admin"
    minio_bucket = f"worker-{get_worker_id()}-<service_name>"

    return Settings(
        schema_=None,
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
                secret_key=SecretStr(SUITE_MINIO_SECRET_KEY),
                bucket=minio_bucket.replace("<service_name>", "clubs"),
            ),
        ),
        student_affairs_service=StudentAffairsSettings(
            environment=Environment.TESTING,
            omnidesk=OmnideskSettings(jwt_marker=SecretStr("test-marker-0123456789abcdef")),
        ),
    )


def _wait_mongo_ready(uri: str, deadline_s: float = 30) -> None:
    deadline = time.monotonic() + deadline_s
    client: MongoClient | None = None

    while True:
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=1000)
            client.admin.command("ping")
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)
        finally:
            if client is not None:
                client.close()


def _wait_minio_ready(deadline_s: float = 30) -> None:
    deadline = time.monotonic() + deadline_s

    while True:
        try:
            mc = Minio(
                endpoint=SUITE_MINIO_ENDPOINT,
                access_key=SUITE_MINIO_ACCESS_KEY,
                secret_key=SUITE_MINIO_SECRET_KEY,
                secure=False,
            )
            mc.list_buckets()
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)


suite_timings_stash_key: pytest.StashKey[dict[str, float]] = pytest.StashKey()
suite_monkeypatch_stash_key: pytest.StashKey[pytest.MonkeyPatch] = pytest.StashKey()


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    if getattr(config.option, "collectonly", False):
        return

    if not is_xdist_worker():  # Run only on master worker
        timings: dict[str, float] = {}
        config.stash[suite_timings_stash_key] = timings

        t_suite = time.perf_counter()

        t0 = time.perf_counter()
        _wait_mongo_ready(
            f"mongodb://{SUITE_MONGO_USER}:{SUITE_MONGO_PASSWORD}@{SUITE_MONGO_NETLOC}/admin?authSource=admin"
        )
        timings["infra.mongo_wait_ready_s"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        _wait_minio_ready()
        timings["infra.minio_wait_ready_s"] = time.perf_counter() - t0

        timings["infra.total_start_s"] = time.perf_counter() - t_suite

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
