__all__ = ["INH_TOKEN_AUTH", "get_innohassle_token_auth"]

from typing import Annotated, ClassVar

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.inh_accounts_sdk import UserTokenData, inh_accounts
from src.logging_ import logger

bearer_scheme = HTTPBearer(
    scheme_name="Bearer",
    description=(
        "Token from [InNoHassle Accounts](https://innohassle.ru/account/token) (`JWT`).\n\n"
        "When **`accounts.mock`** is enabled (development-only; gated in settings): the Bearer "
        "credential may instead be JSON with `innohassle_id`, `email`, and optional `telegram_id` "
        "(same shape as user token payload; see **`UserTokenData`** in schemas)."
    ),
    bearerFormat="JWT",
    auto_error=False,  # We'll handle error manually
)


class IncorrectCredentialsException(HTTPException):
    """
    HTTP_401_UNAUTHORIZED
    """

    def __init__(self, no_credentials: bool = False):
        if no_credentials:
            super().__init__(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credentials not provided",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            super().__init__(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to verify credentials",
            )

    responses: ClassVar = {401: {"description": "Unable to verify credentials OR Credentials not provided"}}


class NotAdminException(HTTPException):
    """
    HTTP_403_FORBIDDEN
    """

    def __init__(self):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=self.responses[403]["description"])

    responses: ClassVar = {403: {"description": "You are not an admin, not allowed to access this endpoint"}}


async def get_innohassle_token_auth(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UserTokenData:
    # Prefer header to cookie
    token = bearer and bearer.credentials
    if not token:
        raise IncorrectCredentialsException(no_credentials=True)
    token_data = inh_accounts.decode_user_token(token)
    if token_data is None:
        raise IncorrectCredentialsException(no_credentials=False)
    return token_data


INH_TOKEN_AUTH = Annotated[UserTokenData, Depends(get_innohassle_token_auth)]
"Dependency to get current user authentication data from InNoHassle Accounts Token"


async def ensure_innohassle_admin(auth: INH_TOKEN_AUTH):
    innohassle_user = await inh_accounts.get_user(innohassle_id=auth.innohassle_id)
    if not innohassle_user or not innohassle_user.innohassle_admin:
        logger.warning(
            f"User {auth.innohassle_id} ({auth.email}) is not an admin, but tried to access admin-only endpoint"
        )
        raise NotAdminException()
    return auth


INH_ADMIN_AUTH = Annotated[UserTokenData, Depends(ensure_innohassle_admin)]
"Dependency to get current user authentication data from InNoHassle Accounts Token and ensure he is an admin"
