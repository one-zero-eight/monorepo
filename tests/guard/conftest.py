from collections.abc import Awaitable, Callable
from typing import Any, cast

import pytest
from beanie import PydanticObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.common_beanie import BeanieStore
from src.guard.modules.google_.repository import google_file_repository
from tests.guard.constants import (
    GUARD_AUTHOR_EMAIL,
    GUARD_AUTHOR_OBJECT_ID,
    GUARD_OTHER_EMAIL,
    GUARD_OTHER_OBJECT_ID,
)


@pytest.fixture(scope="session")
def guard_client(request: pytest.FixtureRequest):
    request.getfixturevalue("mock_inh_accounts_http")
    from src.guard import app as guard_app

    with TestClient(guard_app.app) as client:
        yield client


@pytest.fixture(scope="session")
def guard_author_headers(auth_header_factory):
    return auth_header_factory(GUARD_AUTHOR_OBJECT_ID, GUARD_AUTHOR_EMAIL)


@pytest.fixture(scope="session")
def guard_other_headers(auth_header_factory):
    return auth_header_factory(GUARD_OTHER_OBJECT_ID, GUARD_OTHER_EMAIL)


@pytest.fixture
def google_file_factory() -> Callable[..., Awaitable[Any]]:
    async def _create(**kwargs: Any):
        defaults: dict[str, Any] = {
            "author_id": PydanticObjectId(GUARD_AUTHOR_OBJECT_ID),
            "default_role": "reader",
            "file_id": "google-file-id-1",
            "file_type": "spreadsheet",
            "title": "Test Sheet",
            "owner_gmail": "owner@gmail.com",
            "owner_permission_id": "perm-1",
        }
        defaults.update(kwargs)
        return await google_file_repository.create_file(**defaults)

    return _create


@pytest.fixture
def guard_portal(guard_client: TestClient):
    portal = guard_client.portal
    assert portal is not None
    return portal


@pytest.fixture
def create_google_file(guard_portal, google_file_factory):
    def _create(**kwargs: Any):
        async def _run():
            return await google_file_factory(**kwargs)

        return guard_portal.call(_run)

    return _create


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
