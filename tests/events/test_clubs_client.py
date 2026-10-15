from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
import respx

from src.clients.clubs import ApiError, ResponseValidationError, TransportError
from src.events.clubs_client import ClubInfo, ClubsClient
from src.events.schemas import OwnedClub
from tests.events.conftest import CLUB_ID, CLUB_ID_2, CLUB_SLUG, CLUB_TITLE, club_payload

API_URL = "https://clubs.test/api"


@pytest_asyncio.fixture
async def adapter() -> AsyncIterator[ClubsClient]:
    client = ClubsClient(f"{API_URL}/", "service-key")
    try:
        yield client
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_list_owned_clubs_preserves_local_dto(adapter: ClubsClient, respx_mock: respx.MockRouter):
    route = respx_mock.get(f"{API_URL}/clubs/owned-by/leader").respond(
        200, json=[{"club_id": CLUB_ID, "title": CLUB_TITLE}]
    )

    clubs = await adapter.list_owned_clubs("leader")

    assert clubs == [OwnedClub(club_id=CLUB_ID, title=CLUB_TITLE)]
    assert route.calls.last.request.headers["Authorization"] == "Bearer service-key"


@pytest.mark.asyncio
async def test_list_all_clubs_maps_complete_callee_response(adapter: ClubsClient, respx_mock: respx.MockRouter):
    route = respx_mock.get(f"{API_URL}/clubs/").respond(200, json=[club_payload()])

    clubs = await adapter.list_all_clubs()

    assert clubs == [OwnedClub(club_id=CLUB_ID, title=CLUB_TITLE)]
    assert route.calls.last.request.headers["Authorization"] == "Bearer service-key"


@pytest.mark.asyncio
async def test_get_clubs_omits_only_missing_clubs(adapter: ClubsClient, respx_mock: respx.MockRouter):
    route = respx_mock.get(f"{API_URL}/clubs/by-id/{CLUB_ID}").respond(200, json=club_payload())
    respx_mock.get(f"{API_URL}/clubs/by-id/{CLUB_ID_2}").respond(404, json={"detail": "Club not found"})

    clubs = await adapter.get_clubs({CLUB_ID, CLUB_ID_2})

    assert clubs == {CLUB_ID: ClubInfo(id=CLUB_ID, title=CLUB_TITLE, slug=CLUB_SLUG)}
    assert route.calls.last.request.headers["Authorization"] == "Bearer service-key"


@pytest.mark.asyncio
async def test_get_clubs_empty_ids_do_not_request(adapter: ClubsClient, respx_mock: respx.MockRouter):
    assert await adapter.get_clubs(set()) == {}
    assert not respx_mock.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 500, 503])
async def test_get_clubs_propagates_other_api_failures(adapter: ClubsClient, respx_mock: respx.MockRouter, status: int):
    respx_mock.get(f"{API_URL}/clubs/by-id/{CLUB_ID}").respond(status, json={"detail": "Unavailable"})

    with pytest.raises(ApiError) as error:
        await adapter.get_clubs({CLUB_ID})

    assert error.value.status_code == status


@pytest.mark.asyncio
async def test_get_clubs_rejects_incomplete_callee_payload(adapter: ClubsClient, respx_mock: respx.MockRouter):
    respx_mock.get(f"{API_URL}/clubs/by-id/{CLUB_ID}").respond(
        200, json={"id": CLUB_ID, "slug": CLUB_SLUG, "title": CLUB_TITLE}
    )

    with pytest.raises(ResponseValidationError):
        await adapter.get_clubs({CLUB_ID})


@pytest.mark.asyncio
async def test_get_clubs_propagates_transport_failure(adapter: ClubsClient, respx_mock: respx.MockRouter):
    respx_mock.get(f"{API_URL}/clubs/by-id/{CLUB_ID}").mock(side_effect=httpx.ConnectError("Unavailable"))

    with pytest.raises(TransportError):
        await adapter.get_clubs({CLUB_ID})


@pytest.mark.asyncio
async def test_adapter_close_releases_transport_and_allows_reopening(
    adapter: ClubsClient, respx_mock: respx.MockRouter
):
    route = respx_mock.get(f"{API_URL}/clubs/").respond(200, json=[club_payload()])
    expected = [OwnedClub(club_id=CLUB_ID, title=CLUB_TITLE)]

    await adapter.aclose()
    assert await adapter.list_all_clubs() == expected
    first_http = adapter._http
    assert first_http is not None
    assert await adapter.list_all_clubs() == expected
    assert adapter._http is first_http

    await adapter.aclose()
    assert first_http.is_closed
    await adapter.aclose()

    assert await adapter.list_all_clubs() == expected
    second_http = adapter._http
    assert second_http is not None
    assert second_http is not first_http
    assert not second_http.is_closed
    assert len(route.calls) == 3

    await adapter.aclose()
    assert second_http.is_closed
