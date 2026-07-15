__all__ = [
    "ApiKeyDep",
    "AuthContext",
    "RoomTvDep",
    "VerifiedDep",
    "VerifiedOrApiKeyDep",
    "VerifiedOrApiKeyOrRoomTvDep",
    "VerifiedOrRoomTvDep",
]

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.dependencies import INH_TOKEN_AUTH, IncorrectCredentialsException, get_innohassle_token_auth
from src.inh_accounts_sdk import UserTokenData, inh_accounts
from src.room_booking.config import settings
from src.room_booking.config_schema import Room
from src.room_booking.modules.rooms.repository import room_repository

VerifiedDep = INH_TOKEN_AUTH


@dataclass(frozen=True)
class AuthContext:
    user: UserTokenData | None
    room: Room | None
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


async def room_tv_dep(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    if bearer is None:
        raise IncorrectCredentialsException(no_credentials=True)
    token = bearer.credentials
    if not token:
        raise IncorrectCredentialsException(no_credentials=True)
    token_data = inh_accounts.decode_room_tv_token(token)
    if token_data is None:
        raise IncorrectCredentialsException(no_credentials=False)
    room = room_repository.get_by_id(token_data.room_id)
    if room is None:
        raise IncorrectCredentialsException(no_credentials=False)
    return AuthContext(user=None, room=room, is_service=False)


RoomTvDep = Annotated[str, Depends(room_tv_dep)]
"""
Dependency for checking if the request is from public room TV.
"""


async def verify_user_or_api_key(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    token = bearer and bearer.credentials
    if not token:
        raise IncorrectCredentialsException(no_credentials=True)
    if token == settings.api_key.get_secret_value():
        return AuthContext(user=None, room=None, is_service=True)

    token_data = await get_innohassle_token_auth(bearer)
    return AuthContext(user=token_data, room=None, is_service=False)


async def verify_user_or_room_tv(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    try:
        token_data = await get_innohassle_token_auth(bearer)
        return AuthContext(user=token_data, room=None, is_service=False)
    except IncorrectCredentialsException as e:
        user_exception = e
    try:
        return await room_tv_dep(bearer)
    except IncorrectCredentialsException as e:
        room_exception = e

    if user_exception:
        raise user_exception
    raise room_exception


async def verify_user_or_api_key_or_room_tv(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthContext:
    try:
        return await verify_user_or_api_key(bearer)
    except IncorrectCredentialsException as e:
        user_or_api_key_exception = e
    try:
        return await room_tv_dep(bearer)
    except IncorrectCredentialsException as e:
        room_exception = e

    if user_or_api_key_exception:
        raise user_or_api_key_exception
    raise room_exception


VerifiedOrApiKeyDep = Annotated[AuthContext, Depends(verify_user_or_api_key)]
"""
Dependency that accepts either a user JWT or the service api_key.
"""

VerifiedOrRoomTvDep = Annotated[AuthContext, Depends(verify_user_or_room_tv)]
"""
Dependency that accepts either a user JWT or a room TV JWT.
"""

VerifiedOrApiKeyOrRoomTvDep = Annotated[AuthContext, Depends(verify_user_or_api_key_or_room_tv)]
"""
Dependency that accepts either a user JWT or the service api_key or a room TV JWT.
"""
