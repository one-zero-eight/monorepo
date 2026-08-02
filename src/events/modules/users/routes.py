from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.dependencies import INH_TOKEN_AUTH
from src.events.dependencies import ROLES
from src.events.schemas import MeOut

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.get("/me")
async def get_me(auth: INH_TOKEN_AUTH, roles: ROLES) -> MeOut:
    """Get the current user's roles and owned clubs."""
    role_names: list[str] = []
    if roles.is_club_leader:
        role_names.append("club-leader")
    if roles.is_event_manager:
        role_names.append("event-manager")
    if roles.is_moderator:
        role_names.append("moderator")
    return MeOut(roles=role_names, clubs=roles.clubs)
