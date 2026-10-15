__all__ = [
    "CurrentUserIdDep",
    "VerifyParserDep",
    "VerifyParserOrAdminDep",
    "get_current_user_id",
    "verify_parser",
    "verify_parser_or_admin",
]

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from joserfc.errors import JoseError

from src.inh_accounts_sdk import inh_accounts
from src.schedule.db import UserRepoDep
from src.schedule.exceptions import ForbiddenException, IncorrectCredentialsException

bearer_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="Token from [InNoHassle Accounts](https://innohassle.ru/account/token)",
    bearerFormat="JWT",
    auto_error=False,
)


async def get_current_user_id(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    users: UserRepoDep,
) -> int:
    if bearer is None:
        raise IncorrectCredentialsException(no_credentials=True)
    token = bearer.credentials
    if not token:
        raise IncorrectCredentialsException(no_credentials=True)
    token_data = inh_accounts.decode_user_token(token)
    if token_data is None:
        raise IncorrectCredentialsException()
    user_id = await users.fetch_user_id_or_create(token_data.innohassle_id)
    if user_id is None:
        raise IncorrectCredentialsException()
    return user_id


def verify_parser(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> bool:
    if bearer is None:
        raise IncorrectCredentialsException(no_credentials=True)
    token = bearer.credentials
    if not token:
        raise IncorrectCredentialsException(no_credentials=True)
    try:
        payload = inh_accounts._get_jwt_claims(token)
        if "parser" in (payload.get("scope") or "").split():
            return True
        raise IncorrectCredentialsException()
    except JoseError:
        raise IncorrectCredentialsException()


async def verify_parser_or_admin(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> bool:
    if bearer is None:
        raise IncorrectCredentialsException(no_credentials=True)
    token = bearer.credentials
    if not token:
        raise IncorrectCredentialsException(no_credentials=True)
    try:
        payload = inh_accounts._get_jwt_claims(token)
        if "parser" in (payload.get("scope") or "").split():
            return True
    except JoseError:
        raise IncorrectCredentialsException()
    token_data = inh_accounts.decode_user_token(token)
    if token_data is None:
        raise IncorrectCredentialsException()
    innohassle_user = await inh_accounts.get_user(innohassle_id=token_data.innohassle_id)
    if innohassle_user is None or not innohassle_user.innohassle_admin:
        raise ForbiddenException()
    return True


CurrentUserIdDep = Annotated[int, Depends(get_current_user_id)]
VerifyParserDep = Annotated[bool, Depends(verify_parser)]
VerifyParserOrAdminDep = Annotated[bool, Depends(verify_parser_or_admin)]
