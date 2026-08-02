"""Events app client, per-test Mongo/MinIO isolation, and Clubs service mock."""

import re
from typing import cast

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.common_beanie import BeanieStore
from src.common_minio import MinioStore

CLUB_ID = "64b7de000000000000000001"


@pytest.fixture(scope="session")
def clubs_owned_by() -> dict[str, list[dict]]:
    """Mapping innohassle_id → list of owned clubs served by the mocked Clubs API."""
    return {}


@pytest.fixture(scope="session")
def mock_clubs_service(clubs_owned_by: dict[str, list[dict]]):
    def handler(request: httpx.Request) -> httpx.Response:
        innohassle_id = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=clubs_owned_by.get(innohassle_id, []))

    from src.events.config import settings

    api_url = settings.clubs.api_url.rstrip("/")

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as respx_mock:
        respx_mock.get(url__regex=rf"{re.escape(api_url)}/clubs/owned-by/.+").mock(side_effect=handler)
        yield


@pytest.fixture(scope="session")
def events_client(request: pytest.FixtureRequest):
    request.getfixturevalue("mock_inh_accounts_http")
    request.getfixturevalue("mock_clubs_service")
    from src.events import app as events_module

    with TestClient(events_module.app) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_up_stores_per_test(request: pytest.FixtureRequest):
    """Shared events DB and MinIO bucket; wipe documents and objects before each test."""
    if "events_client" not in request.fixturenames:
        yield
        return

    client: TestClient = request.getfixturevalue("events_client")
    portal = client.portal
    assert portal is not None

    app = cast(FastAPI, client.app)
    beanie_store: BeanieStore = app.state.beanie_store
    minio_store: MinioStore = app.state.minio_store

    portal.call(beanie_store.clear_database)
    minio_store.clear_bucket()

    yield


@pytest.fixture
def club_leader_headers(auth_header_factory, clubs_owned_by: dict[str, list[dict]]):
    clubs_owned_by["club-leader-1"] = [{"club_id": CLUB_ID, "title": "Test Club"}]
    return auth_header_factory("club-leader-1", "club-leader@innopolis.university")


@pytest.fixture
def plain_user_headers(auth_header_factory):
    return auth_header_factory("plain-user-1", "plain-user@innopolis.university")
