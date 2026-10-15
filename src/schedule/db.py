"""SQLAlchemy engine/session lifecycle — one AsyncSession per request via Depends."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.schedule.modules.event_groups.repository import SqlEventGroupRepository
from src.schedule.modules.events.repository import SqlEventRepository
from src.schedule.modules.tags.repository import SqlTagRepository
from src.schedule.modules.users.repository import SqlUserRepository
from src.schedule.storages.sql import SQLAlchemyStorage


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Request-scoped session. Commit on success, rollback on error."""
    storage: SQLAlchemyStorage = request.app.state.sql_storage
    async with storage.sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_user_repository(session: SessionDep) -> SqlUserRepository:
    return SqlUserRepository(session)


def get_tag_repository(session: SessionDep) -> SqlTagRepository:
    return SqlTagRepository(session)


def get_event_group_repository(session: SessionDep) -> SqlEventGroupRepository:
    return SqlEventGroupRepository(session)


def get_event_repository(session: SessionDep) -> SqlEventRepository:
    return SqlEventRepository(session)


UserRepoDep = Annotated[SqlUserRepository, Depends(get_user_repository)]
TagRepoDep = Annotated[SqlTagRepository, Depends(get_tag_repository)]
EventGroupRepoDep = Annotated[SqlEventGroupRepository, Depends(get_event_group_repository)]
EventRepoDep = Annotated[SqlEventRepository, Depends(get_event_repository)]
