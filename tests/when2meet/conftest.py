from collections.abc import Generator
from typing import Any, cast

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from src.common_beanie import BeanieStore


@pytest.fixture(scope="session")
def when2meet_client() -> Generator[TestClient, Any]:
    from src.when2meet import app as when2meet_app

    with TestClient(when2meet_app.app) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_up_stores_per_test(request: pytest.FixtureRequest):
    if "when2meet_client" not in request.fixturenames:
        yield
        return

    client: TestClient = request.getfixturevalue("when2meet_client")
    portal = client.portal
    assert portal is not None

    app = cast(FastAPI, client.app)
    beanie_store: BeanieStore = app.state.beanie_store

    portal.call(beanie_store.clear_database)

    yield
