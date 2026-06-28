from typing import Annotated

from fastapi import Depends, HTTPException

from src.board_games.modules.users import users_repo
from src.board_games.mongo import User, UserRole
from src.dependencies import INH_TOKEN_AUTH
from src.logging_ import logger


async def ensure_board_games_admin(auth: INH_TOKEN_AUTH):
    user = await users_repo.read_by_innohassle_id(auth.innohassle_id)
    if not user or user.role != UserRole.ADMIN:
        logger.warning(
            f"User {auth.innohassle_id} ({auth.email}) is not an admin in board games service, but tried to access admin-only endpoint"
        )
        raise HTTPException(status_code=403, detail="You are not an admin in board games service")
    return user


BOARD_GAMES_ADMIN_AUTH = Annotated[User, Depends(ensure_board_games_admin)]
