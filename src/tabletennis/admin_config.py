__all__ = ["TABLETENNIS_ADMIN_AUTH", "tabletennis_admin_ids"]

import asyncio
import time as tm
from typing import Annotated

from fastapi import Depends, HTTPException, status

from src.dependencies import INH_TOKEN_AUTH
from src.inh_accounts_sdk import UserTokenData, inh_accounts
from src.logging_ import logger

from .config import settings


async def ensure_tabletennis_admin(auth: INH_TOKEN_AUTH) -> UserTokenData:
    """
    Dependency to ensure the user's email is listed in tabletennis_service.admin_emails.
    """
    if auth.email not in settings.admin_emails:
        logger.warning(f"User {auth.innohassle_id} ({auth.email}) tried to access coach-only endpoint.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a Table Tennis administrator/coach!",
        )
    return auth


async def is_tabletennis_admin(auth: INH_TOKEN_AUTH) -> bool:
    return auth.email in settings.admin_emails


TABLETENNIS_ADMIN_AUTH = Annotated[UserTokenData, Depends(ensure_tabletennis_admin)]


ADMIN_IDS_TTL_SECONDS = 600
_admin_ids_cache: dict[str, tuple[float, frozenset[str]]] = {}


async def _resolve_admin_id(email: str) -> str | None:
    try:
        acc = await inh_accounts.get_user(email=email)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to resolve table tennis admin {email}: {e}")
        return None
    return acc.id if acc else None


async def tabletennis_admin_ids() -> frozenset[str]:
    """
    innohassle_ids of the admins listed in admin_emails, used to mark them in the players list.
    Resolved through InNoHassle Accounts and cached for a few minutes.
    """
    cached = _admin_ids_cache.get("ids")
    if cached and tm.monotonic() - cached[0] < ADMIN_IDS_TTL_SECONDS:
        return cached[1]

    resolved = await asyncio.gather(*(_resolve_admin_id(email) for email in settings.admin_emails))
    ids = frozenset(i for i in resolved if i)
    _admin_ids_cache["ids"] = (tm.monotonic(), ids)
    return ids


def reset_admin_ids_cache() -> None:
    _admin_ids_cache.clear()
