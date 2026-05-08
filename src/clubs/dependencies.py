from typing import Annotated

from fastapi import Depends, HTTPException

from src.clubs.modules.users import users_repo
from src.clubs.mongo import User, UserRole
from src.dependencies import INH_TOKEN_AUTH
from src.logging_ import logger


async def ensure_clubs_admin(auth: INH_TOKEN_AUTH):
    clubs_user = await users_repo.read_by_innohassle_id(auth.innohassle_id)
    if not clubs_user or clubs_user.role != UserRole.ADMIN:
        logger.warning(
            f"User {auth.innohassle_id} ({auth.email}) is not an admin in clubs service, but tried to access admin-only endpoint"
        )
        raise HTTPException(status_code=403, detail="You are not an admin in clubs service")
    return clubs_user


CLUBS_ADMIN_AUTH = Annotated[User, Depends(ensure_clubs_admin)]
