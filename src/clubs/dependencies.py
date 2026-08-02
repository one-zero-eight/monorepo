from typing import Annotated

from beanie import PydanticObjectId
from fastapi import Depends, HTTPException

from src.clubs.modules.clubs import clubs_repo
from src.clubs.modules.users import users_repo
from src.clubs.mongo import Club, User, UserRole
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


async def ensure_club_leader_or_admin(id: PydanticObjectId, auth: INH_TOKEN_AUTH) -> Club:
    club = await clubs_repo.read(id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    clubs_user = await users_repo.read_by_innohassle_id(auth.innohassle_id)
    if clubs_user and clubs_user.role == UserRole.ADMIN:
        return club

    if club.leader_innohassle_id == auth.innohassle_id:
        return club

    logger.warning(
        f"User {auth.innohassle_id} ({auth.email}) is not a leader or admin for club {id}, but tried to upload description image"
    )
    raise HTTPException(status_code=403, detail="Only club leader or admin can upload description images")


CLUBS_ADMIN_AUTH = Annotated[User, Depends(ensure_clubs_admin)]
CLUB_LEADER_OR_ADMIN = Annotated[Club, Depends(ensure_club_leader_or_admin)]
