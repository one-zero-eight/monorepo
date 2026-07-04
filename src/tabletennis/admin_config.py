__all__ = ["TABLETENNIS_ADMIN_AUTH"]

from typing import Annotated

from fastapi import Depends, HTTPException, status

from src.dependencies import INH_TOKEN_AUTH
from src.inh_accounts_sdk import UserTokenData
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


# Твой чистый элиас для routes.py
TABLETENNIS_ADMIN_AUTH = Annotated[UserTokenData, Depends(ensure_tabletennis_admin)]
