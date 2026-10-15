__all__ = [
    "CurrentUserIdDep",
    "EventGroupRepoDep",
    "SessionDep",
    "TagRepoDep",
    "UserRepoDep",
    "VerifyParserDep",
    "VerifyParserOrAdminDep",
    "get_current_user_id",
    "get_event_group_repository",
    "get_session",
    "get_tag_repository",
    "get_user_repository",
    "verify_parser",
    "verify_parser_or_admin",
]

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from joserfc.errors import JoseError
from sqlalchemy.ext.asyncio import AsyncSession

from src.inh_accounts_sdk import inh_accounts
from src.schedule.exceptions import ForbiddenException, IncorrectCredentialsException
from src.schedule.modules.event_groups.repository import SqlEventGroupRepository
from src.schedule.modules.tags.repository import SqlTagRepository
from src.schedule.modules.users.repository import SqlUserRepository
from src.schedule.storage import SQLAlchemyStorage


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


UserRepoDep = Annotated[SqlUserRepository, Depends(get_user_repository)]
TagRepoDep = Annotated[SqlTagRepository, Depends(get_tag_repository)]
EventGroupRepoDep = Annotated[SqlEventGroupRepository, Depends(get_event_group_repository)]

bearer_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="Token from [InNoHassle Accounts](https://innohassle.ru/account/token)",
    bearerFormat="JWT",
    auto_error=False,
)


async def get_current_user_id(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    users: UserRepoDep,
) -> int:
    if bearer is None:
        raise IncorrectCredentialsException(no_credentials=True)
    token = bearer.credentials
    if not token:
        raise IncorrectCredentialsException(no_credentials=True)
    token_data = inh_accounts.decode_user_token(token)
    if token_data is None:
        raise IncorrectCredentialsException()
    user_id = await users.fetch_user_id_or_create(token_data.innohassle_id)
    if user_id is None:
        raise IncorrectCredentialsException()
    return user_id


def verify_parser(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> bool:
    if bearer is None:
        raise IncorrectCredentialsException(no_credentials=True)
    token = bearer.credentials
    if not token:
        raise IncorrectCredentialsException(no_credentials=True)
    try:
        payload = inh_accounts._get_jwt_claims(token)
        if "parser" in (payload.get("scope") or "").split():
            return True
        raise IncorrectCredentialsException()
    except JoseError:
        raise IncorrectCredentialsException()


async def verify_parser_or_admin(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> bool:
    if bearer is None:
        raise IncorrectCredentialsException(no_credentials=True)
    token = bearer.credentials
    if not token:
        raise IncorrectCredentialsException(no_credentials=True)
    try:
        payload = inh_accounts._get_jwt_claims(token)
        if "parser" in (payload.get("scope") or "").split():
            return True
    except JoseError:
        raise IncorrectCredentialsException()
    token_data = inh_accounts.decode_user_token(token)
    if token_data is None:
        raise IncorrectCredentialsException()
    innohassle_user = await inh_accounts.get_user(innohassle_id=token_data.innohassle_id)
    if innohassle_user is None or not innohassle_user.innohassle_admin:
        raise ForbiddenException()
    return True


CurrentUserIdDep = Annotated[int, Depends(get_current_user_id)]
VerifyParserDep = Annotated[bool, Depends(verify_parser)]
VerifyParserOrAdminDep = Annotated[bool, Depends(verify_parser_or_admin)]
