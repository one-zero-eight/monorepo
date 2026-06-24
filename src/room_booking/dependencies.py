__all__ = ["ApiKeyDep", "AuthContext", "VerifiedDep", "VerifiedOrApiKeyDep"]

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.dependencies import INH_TOKEN_AUTH, IncorrectCredentialsException, get_innohassle_token_auth
from src.inh_accounts_sdk import UserTokenData
from src.room_booking.config import settings

VerifiedDep = INH_TOKEN_AUTH


@dataclass(frozen=True)
class AuthContext:
    user: UserTokenData | None
    is_service: bool


bearer_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="Token from [InNoHassle Accounts](https://innohassle.ru/account/token)",
    bearerFormat="JWT",
    auto_error=False,
)


def api_key_dep(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if bearer is None or not bearer.credentials:
        raise IncorrectCredentialsException(no_credentials=True)
    token = bearer.credentials
    if token != settings.api_key.get_secret_value():
        raise IncorrectCredentialsException(no_credentials=False)
    return token


ApiKeyDep = Annotated[str, Depends(api_key_dep)]
"""
Dependency for checking if the request is coming from an authorized external service.
"""


async def verify_user_or_api_key(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    token = bearer and bearer.credentials
    if not token:
        raise IncorrectCredentialsException(no_credentials=True)
    if token == settings.api_key.get_secret_value():
        return AuthContext(user=None, is_service=True)

    token_data = await get_innohassle_token_auth(bearer)
    return AuthContext(user=token_data, is_service=False)


VerifiedOrApiKeyDep = Annotated[AuthContext, Depends(verify_user_or_api_key)]
"""
Dependency that accepts either a user JWT or the service api_key.
"""
