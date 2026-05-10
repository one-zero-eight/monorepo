"""Clubs app client and per-test Mongo/MinIO isolation."""

from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.common_beanie import BeanieStore
from src.common_minio import MinioStore


@pytest.fixture(scope="session")
def clubs_client(request: pytest.FixtureRequest):
    request.getfixturevalue("mock_inh_accounts_http")
    from src.clubs import app as clubs_module

    with TestClient(clubs_module.app) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_up_stores_per_test(request: pytest.FixtureRequest):
    """Shared clubs DB and MinIO bucket; wipe documents and objects before each test."""
    if "clubs_client" not in request.fixturenames:
        yield
        return

    client: TestClient = request.getfixturevalue("clubs_client")
    portal = client.portal
    assert portal is not None

    app = cast(FastAPI, client.app)
    beanie_store: BeanieStore = app.state.beanie_store
    minio_store: MinioStore = app.state.minio_store

    portal.call(beanie_store.clear_database)
    minio_store.clear_bucket()

    yield
