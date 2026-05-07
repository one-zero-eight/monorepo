from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from starlette import status

import src.modules.clubs.crud as clubs_crud
import src.modules.users.crud as c
from src.api import docs
from src.api.dependencies import USER_AUTH
from src.config import settings
from src.modules.inh_accounts_sdk import inh_accounts
from src.storages.mongo import Club
from src.storages.mongo.user import UserRole, UserSchema

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    route_class=AutoDeriveResponsesAPIRoute,
)
_description = """
User information.
"""
docs.TAGS_INFO.append({"description": _description, "name": str(router.tags[0])})


class UserWithClubs(UserSchema):
    leader_in_clubs: list[Club]
    "List of clubs which you are a leader of"


@router.get(
    "/me",
    responses={
        status.HTTP_200_OK: {"description": "Current user info"},
    },
)
async def get_me(current_user: USER_AUTH) -> UserWithClubs:
    """Get current user's information with related clubs if authenticated."""
    user_data = await c.read_by_innohassle_id(current_user.innohassle_id)
    leader_in_clubs = await clubs_crud.read_by_leader_innohassle_id(current_user.innohassle_id)
    return UserWithClubs(
        innohassle_id=current_user.innohassle_id,
        role=user_data.role if user_data else UserRole.DEFAULT,
        leader_in_clubs=leader_in_clubs,
    )


@router.post(
    "/change_role",
    responses={
        status.HTTP_200_OK: {"description": "Role changed successfully"},
        status.HTTP_403_FORBIDDEN: {"description": "Only superadmins can change role"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found in InNoHassle Accounts"},
    },
)
async def change_role(
    role: UserRole,
    user_to_change_email: str,
    current_user: USER_AUTH,
) -> None:
    """Change role of user by email."""
    if current_user.email not in settings.superadmin_emails:
        raise HTTPException(status_code=403, detail="Only superadmin can change role")
    user_to_change = await inh_accounts.get_user(email=user_to_change_email)
    if not user_to_change:
        raise HTTPException(status_code=404, detail="User to change not found")
    await c.change_role_of_user(user_to_change.id, role)
