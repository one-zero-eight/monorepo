"""Forms app client and per-test Mongo isolation."""

from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.common_beanie import BeanieStore


@pytest.fixture(scope="session")
def forms_client(request: pytest.FixtureRequest):
    request.getfixturevalue("mock_inh_accounts_http")
    from src.forms import app as forms_app

    with TestClient(forms_app.app) as client:
        yield client


@pytest.fixture(autouse=True)
def _cleanup(request: pytest.FixtureRequest):
    if "forms_client" not in request.fixturenames:
        yield
        return
    client: TestClient = request.getfixturevalue("forms_client")
    portal = client.portal
    assert portal is not None
    app = cast(FastAPI, client.app)
    beanie_store: BeanieStore = app.state.beanie_store
    portal.call(beanie_store.clear_database)
    yield
