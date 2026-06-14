from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.common_beanie import BeanieStore


@pytest.fixture(scope="session")
def guard_client(request: pytest.FixtureRequest):
    request.getfixturevalue("mock_inh_accounts_http")
    from src.guard import app as guard_app

    with TestClient(guard_app.app) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_up_stores_per_test(request: pytest.FixtureRequest):
    if "guard_client" not in request.fixturenames:
        yield
        return

    client: TestClient = request.getfixturevalue("guard_client")
    portal = client.portal
    assert portal is not None
    app = cast(FastAPI, client.app)
    beanie_store: BeanieStore = app.state.beanie_store
    portal.call(beanie_store.clear_database)
    yield
