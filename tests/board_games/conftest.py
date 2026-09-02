from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.common_beanie import BeanieStore
from src.common_minio import MinioStore


@pytest.fixture(scope="session")
def board_games_client(request: pytest.FixtureRequest):
    request.getfixturevalue("mock_inh_accounts_http")
    from src.board_games import app as board_games_module

    with TestClient(board_games_module.app) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_up_stores_per_test(request: pytest.FixtureRequest):
    if "board_games_client" not in request.fixturenames:
        yield
        return

    client: TestClient = request.getfixturevalue("board_games_client")
    portal = client.portal
    assert portal is not None

    app = cast(FastAPI, client.app)
    beanie_store: BeanieStore = app.state.beanie_store
    minio_store: MinioStore = app.state.minio_store

    portal.call(beanie_store.clear_database)
    minio_store.clear_bucket()

    yield
