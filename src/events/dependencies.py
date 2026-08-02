from typing import Annotated

from fastapi import Depends, HTTPException

from src.dependencies import INH_TOKEN_AUTH
from src.events.clubs_client import clubs_client
from src.events.config import settings
from src.events.schemas import UserRoles
from src.inh_accounts_sdk import UserTokenData


def _email_in_list(email: str, emails: list[str]) -> bool:
    normalized = email.casefold()
    return any(entry.casefold() == normalized for entry in emails)


async def get_user_roles(auth: INH_TOKEN_AUTH) -> UserRoles:
    clubs = await clubs_client.list_owned_clubs(auth.innohassle_id)
    return UserRoles(
        innohassle_id=auth.innohassle_id,
        is_club_leader=bool(clubs),
        is_event_manager=_email_in_list(auth.email, settings.event_manager_emails),
        is_moderator=_email_in_list(auth.email, settings.moderator_emails),
        clubs=clubs,
    )


ROLES = Annotated[UserRoles, Depends(get_user_roles)]
"Roles of the current user: club leader / event manager / moderator (roles sum up)"


async def ensure_moderator(auth: INH_TOKEN_AUTH) -> UserTokenData:
    if not _email_in_list(auth.email, settings.moderator_emails):
        raise HTTPException(status_code=403, detail="Only moderators can perform this action")
    return auth


MODERATOR_AUTH = Annotated[UserTokenData, Depends(ensure_moderator)]
