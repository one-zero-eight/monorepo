__all__ = ["INH_TOKEN_AUTH", "get_innohassle_token_auth"]

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.inh_accounts_sdk import UserTokenData, inh_accounts

bearer_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="Token from [InNoHassle Accounts](https://innohassle.ru/account/token)",
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

    responses = {401: {"description": "Unable to verify credentials OR Credentials not provided"}}


async def get_innohassle_token_auth(
    bearer: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
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
