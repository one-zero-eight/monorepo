from typing import Annotated

from fastapi import Depends, HTTPException

from src.dependencies import INH_TOKEN_AUTH, OPTIONAL_INH_TOKEN_AUTH
from src.events.clubs_client import clubs_client
from src.events.config import settings
from src.events.schemas import UserRoles
from src.inh_accounts_sdk import UserTokenData


def _email_in_list(email: str, emails: list[str]) -> bool:
    normalized = email.casefold()
    return any(entry.casefold() == normalized for entry in emails)


async def resolve_user_roles(auth: UserTokenData) -> UserRoles:
    is_club_moderator = _email_in_list(auth.email, settings.club_moderator_emails)
    if is_club_moderator:
        clubs = await clubs_client.list_all_clubs()
    else:
        clubs = await clubs_client.list_owned_clubs(auth.innohassle_id)
    return UserRoles(
        innohassle_id=auth.innohassle_id,
        is_club_leader=bool(clubs),
        is_event_manager=_email_in_list(auth.email, settings.event_manager_emails),
        is_moderator=_email_in_list(auth.email, settings.moderator_emails),
        is_club_moderator=is_club_moderator,
        clubs=clubs,
    )


async def get_user_roles(auth: INH_TOKEN_AUTH) -> UserRoles:
    return await resolve_user_roles(auth)


async def get_optional_user_roles(auth: OPTIONAL_INH_TOKEN_AUTH) -> UserRoles | None:
    if auth is None:
        return None
    return await resolve_user_roles(auth)


ROLES = Annotated[UserRoles, Depends(get_user_roles)]
"Roles of the current user: club leader / event manager / moderator (roles sum up)"

OPTIONAL_ROLES = Annotated[UserRoles | None, Depends(get_optional_user_roles)]
"Roles when authenticated; None for anonymous requests"


async def ensure_moderator(auth: INH_TOKEN_AUTH) -> UserTokenData:
    if not _email_in_list(auth.email, settings.moderator_emails):
        raise HTTPException(status_code=403, detail="Only moderators can perform this action")
    return auth


MODERATOR_AUTH = Annotated[UserTokenData, Depends(ensure_moderator)]
