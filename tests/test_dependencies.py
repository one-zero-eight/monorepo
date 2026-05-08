import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import src.dependencies as dependencies
from src.dependencies import (
    IncorrectCredentialsException,
    NotAdminException,
    ensure_innohassle_admin,
    get_innohassle_token_auth,
)
from src.inh_accounts_sdk import UserTokenData, inh_accounts


def test_incorrect_credentials_exception_both_variants():
    missing = IncorrectCredentialsException(no_credentials=True)
    assert missing.status_code == 401
    assert missing.detail == "Credentials not provided"
    assert missing.headers == {"WWW-Authenticate": "Bearer"}
    invalid = IncorrectCredentialsException(no_credentials=False)
    assert invalid.status_code == 401
    assert invalid.detail == "Unable to verify credentials"


def test_not_admin_exception():
    exc = NotAdminException()
    assert exc.status_code == 403
    assert exc.detail == NotAdminException.responses[403]["description"]


def test_dependency_exports_reference_fastapi_depends():
    assert "INH_TOKEN_AUTH" in dependencies.__all__
    assert dependencies.INH_TOKEN_AUTH is not None
    assert dependencies.INH_ADMIN_AUTH is not None


@pytest.mark.asyncio
async def test_get_innohassle_token_auth_uses_decode_user_token(monkeypatch):
    monkeypatch.setattr(
        inh_accounts,
        "decode_user_token",
        lambda _token: UserTokenData(innohassle_id="mock-id", email="mock@innopolis.university"),
    )
    bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials="any")
    data = await get_innohassle_token_auth(bearer)
    assert data.innohassle_id == "mock-id"
    assert data.email == "mock@innopolis.university"


@pytest.mark.asyncio
async def test_get_innohassle_token_auth_requires_credentials():
    with pytest.raises(IncorrectCredentialsException) as exc_info:
        await get_innohassle_token_auth(None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Credentials not provided"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.asyncio
async def test_get_innohassle_token_auth_rejects_invalid_token():
    await inh_accounts.update_key_set()
    bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt")

    with pytest.raises(IncorrectCredentialsException) as exc_info:
        await get_innohassle_token_auth(bearer)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Unable to verify credentials"


@pytest.mark.asyncio
async def test_get_innohassle_token_auth_accepts_valid_token(make_user_token):
    await inh_accounts.update_key_set()
    token = make_user_token(uid="test-user-1", email="test-user-1@innopolis.university")
    bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    token_data = await get_innohassle_token_auth(bearer)
    assert token_data.innohassle_id == "test-user-1"
    assert token_data.email == "test-user-1@innopolis.university"


@pytest.mark.asyncio
async def test_ensure_innohassle_admin_allows_admin():
    auth = UserTokenData(innohassle_id="superadmin-1", email="admin@innopolis.university")
    result = await ensure_innohassle_admin(auth)
    assert result == auth


@pytest.mark.asyncio
async def test_ensure_innohassle_admin_rejects_non_admin():
    auth = UserTokenData(innohassle_id="test-user-1", email="test-user-1@innopolis.university")

    with pytest.raises(NotAdminException) as exc_info:
        await ensure_innohassle_admin(auth)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "You are not an admin, not allowed to access this endpoint"


@pytest.mark.asyncio
async def test_ensure_innohassle_admin_rejects_missing_user():
    auth = UserTokenData(innohassle_id="missing-user", email="missing@innopolis.university")

    with pytest.raises(HTTPException) as exc_info:
        await ensure_innohassle_admin(auth)

    assert exc_info.value.status_code == 403
