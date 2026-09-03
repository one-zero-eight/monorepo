from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.common_beanie import BeanieStore

TABLETENNIS_ADMIN_EMAIL = "tt-admin@innopolis.university"


@pytest.fixture(scope="session")
def tabletennis_client(request: pytest.FixtureRequest):
    request.getfixturevalue("mock_inh_accounts_http")
    from src.migrations import migrate_service

    migrate_service("tabletennis")
    from src.tabletennis.config import settings

    settings.admin_emails.append(TABLETENNIS_ADMIN_EMAIL)

    from src.tabletennis import app as tabletennis_app

    with TestClient(tabletennis_app.app) as client:
        yield client


@pytest.fixture(scope="session")
def admin_headers(tabletennis_client: TestClient, auth_header_factory):
    return auth_header_factory("tt-admin-1", TABLETENNIS_ADMIN_EMAIL)


@pytest.fixture(autouse=True)
def clean_up_stores_per_test(request: pytest.FixtureRequest):
    """Shared tabletennis DB; wipe documents before each test."""
    if "tabletennis_client" not in request.fixturenames:
        yield
        return

    client: TestClient = request.getfixturevalue("tabletennis_client")
    portal = client.portal
    assert portal is not None

    app = cast(FastAPI, client.app)
    beanie_store: BeanieStore = app.state.beanie_store

    portal.call(beanie_store.clear_database)

    yield
