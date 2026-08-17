import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_app_is_running(fastapi_test_client: AsyncClient) -> None:
    response = await fastapi_test_client.get("/", follow_redirects=True)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_failed(fastapi_test_client: AsyncClient) -> None:
    response = await fastapi_test_client.post("/parser/parse-location-string", params={"location_string": "107"})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_auth_success(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        url="/parser/parse-location-string",
        params={"location_string": "107"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_booking_review_requires_term(
    authenticated_client: AsyncClient,
    bookings_repo,
    mock_booking_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    response = await authenticated_client.get("/bookings/review")
    assert response.status_code == 404
