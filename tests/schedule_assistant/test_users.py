import pytest
from httpx import ASGITransport, AsyncClient

from src.inh_accounts_sdk import UserTokenData
from src.schedule_assistant.dependencies import verify_token_dep


@pytest.mark.asyncio
async def test_me_requires_auth(fastapi_test_client: AsyncClient) -> None:
    response = await fastapi_test_client.get("/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_moderator_false(fastapi_app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.moderator_emails",
        ["moderator@innopolis.university"],
    )

    async def fake_verify_token_dep() -> tuple[UserTokenData, str]:
        return UserTokenData(innohassle_id="123", email="user@innopolis.university"), "token"

    fastapi_app.dependency_overrides[verify_token_dep] = fake_verify_token_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
            response = await client.get("/me")
    finally:
        fastapi_app.dependency_overrides.pop(verify_token_dep)

    assert response.status_code == 200
    assert response.json() == {
        "email": "user@innopolis.university",
        "is_moderator": False,
    }


@pytest.mark.asyncio
async def test_me_returns_moderator_true(fastapi_app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.moderator_emails",
        ["moderator@innopolis.university"],
    )

    async def fake_verify_token_dep() -> tuple[UserTokenData, str]:
        return UserTokenData(innohassle_id="123", email="moderator@innopolis.university"), "token"

    fastapi_app.dependency_overrides[verify_token_dep] = fake_verify_token_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
            response = await client.get("/me")
    finally:
        fastapi_app.dependency_overrides.pop(verify_token_dep)

    assert response.status_code == 200
    assert response.json() == {
        "email": "moderator@innopolis.university",
        "is_moderator": True,
    }
