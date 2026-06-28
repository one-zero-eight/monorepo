from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from starlette import status

from src.board_games.config import settings
from src.board_games.modules.users import users_repo
from src.board_games.mongo import UserRole, UserSchema
from src.dependencies import INH_TOKEN_AUTH
from src.inh_accounts_sdk import inh_accounts
from src.logging_ import logger

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.get("/me")
async def get_me(current_user: INH_TOKEN_AUTH) -> UserSchema:
    user_data = await users_repo.read_by_innohassle_id(current_user.innohassle_id)
    return UserSchema(
        innohassle_id=current_user.innohassle_id,
        role=user_data.role if user_data else UserRole.DEFAULT,
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
    current_user: INH_TOKEN_AUTH,
) -> None:
    if current_user.email not in settings.superadmin_emails:
        logger.warning(
            f"User {current_user.email} tried to change board games role of {user_to_change_email} to {role} but is not a superadmin"
        )
        raise HTTPException(status_code=403, detail="Only superadmin can change role")
    user_to_change = await inh_accounts.get_user(email=user_to_change_email)
    if not user_to_change:
        raise HTTPException(status_code=404, detail="User to change not found")
    await users_repo.change_role_of_user(user_to_change.id, role)
