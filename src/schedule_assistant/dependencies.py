__all__ = [
    "DistributionUploadRepoDep",
    "ModeratorDep",
    "PreferenceInviteRepoDep",
    "ScheduleConfigRepoDep",
    "ServiceApiKeyDep",
    "SessionDep",
    "VerifyTokenDep",
    "get_distribution_upload_repository",
    "get_preference_invite_repository",
    "get_schedule_config_repository",
    "get_session",
    "is_moderator_email",
    "verify_moderator_dep",
    "verify_service_api_key",
    "verify_token_dep",
]

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from src.inh_accounts_sdk import UserTokenData, inh_accounts
from src.schedule_assistant.config import settings
from src.schedule_assistant.modules.distributions.repository import DistributionUploadRepository
from src.schedule_assistant.modules.instructor_preferences.repository import PreferenceInviteRepository
from src.schedule_assistant.modules.schedule_config.repository import ScheduleConfigRepository

bearer_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="Token from [InNoHassle Accounts](https://innohassle.ru/account/token)",
    bearerFormat="JWT",
    auto_error=False,
)


def get_session(request: Request) -> Generator[Session]:
    """Request-scoped session. Commit on success, rollback on error."""
    factory: sessionmaker[Session] = request.app.state.sessionmaker
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]


def get_schedule_config_repository(session: SessionDep) -> ScheduleConfigRepository:
    return ScheduleConfigRepository(session)


def get_preference_invite_repository(session: SessionDep) -> PreferenceInviteRepository:
    return PreferenceInviteRepository(session)


def get_distribution_upload_repository(session: SessionDep) -> DistributionUploadRepository:
    return DistributionUploadRepository(session)


ScheduleConfigRepoDep = Annotated[ScheduleConfigRepository, Depends(get_schedule_config_repository)]
PreferenceInviteRepoDep = Annotated[PreferenceInviteRepository, Depends(get_preference_invite_repository)]
DistributionUploadRepoDep = Annotated[DistributionUploadRepository, Depends(get_distribution_upload_repository)]


async def verify_service_api_key(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if bearer is None or not bearer.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No credentials provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if bearer.credentials != settings.api_key.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return bearer.credentials


ServiceApiKeyDep = Annotated[str, Depends(verify_service_api_key)]


async def verify_token_dep(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> tuple[UserTokenData, str]:
    if bearer is None or not bearer.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No credentials provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = bearer.credentials
    token_data = inh_accounts.decode_user_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data, token


VerifyTokenDep = Annotated[tuple[UserTokenData, str], Depends(verify_token_dep)]


def is_moderator_email(email: str) -> bool:
    normalized = email.casefold()
    return any(moderator_email.casefold() == normalized for moderator_email in settings.moderator_emails)


async def verify_moderator_dep(
    user_and_token: VerifyTokenDep,
) -> tuple[UserTokenData, str]:
    user, token = user_and_token
    if not is_moderator_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a moderator",
        )
    return user, token


ModeratorDep = Annotated[tuple[UserTokenData, str], Depends(verify_moderator_dep)]
