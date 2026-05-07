__all__ = ["USER_AUTH", "get_current_user_auth"]

from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import src.modules.users.crud as users_crud
from src.api.exceptions import IncorrectCredentialsException
from src.modules.inh_accounts_sdk import UserTokenData, inh_accounts
from src.storages.mongo.user import UserRole

bearer_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="Token from [InNoHassle Accounts](https://innohassle.ru/account/token)",
    bearerFormat="JWT",
    auto_error=False,  # We'll handle error manually
)


async def get_current_user_auth(
    bearer: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserTokenData:
    # Prefer header to cookie
    token = bearer and bearer.credentials
    if not token:
        raise IncorrectCredentialsException(no_credentials=True)
    token_data = inh_accounts.decode_token(token)
    if token_data is None:
        raise IncorrectCredentialsException(no_credentials=False)
    return token_data


USER_AUTH = Annotated[UserTokenData, Depends(get_current_user_auth)]


async def require_admin(current_user: USER_AUTH):
    innohassle_user = await users_crud.read_by_innohassle_id(current_user.innohassle_id)
    if not innohassle_user or innohassle_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="You are not an admin")
    return current_user


REQUIRE_ADMIN = Annotated[UserTokenData, Depends(require_admin)]
