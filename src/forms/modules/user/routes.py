"""
User data, registration, login, logout.
"""

from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.dependencies import INH_TOKEN_AUTH
from src.inh_accounts_sdk import UserSchema, inh_accounts

router = APIRouter(
    prefix="/user",
    tags=["User"],
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.get("/me", responses={200: {"description": "Current user info"}})
async def get_me(auth: INH_TOKEN_AUTH) -> UserSchema:
    """
    Get current user info if authenticated
    """

    user = await inh_accounts.get_user(auth.innohassle_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
