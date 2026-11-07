__all__ = [
    "DistributionUploadRepoDep",
    "ModeratorDep",
    "PreferenceInviteRepoDep",
    "ScheduleConfigRepoDep",
    "ServiceTokenDep",
    "SessionDep",
    "VerifyTokenDep",
    "get_distribution_upload_repository",
    "get_preference_invite_repository",
    "get_schedule_config_repository",
    "get_session",
    "is_moderator_email",
    "verify_moderator_dep",
    "verify_service_email_access",
    "verify_service_token",
    "verify_token_dep",
]

from collections.abc import Generator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from src.dependencies import service_token_scopes
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


SERVICE_SCOPE = "users"
"Scope of the InNoHassle Accounts service JWT (`accounts.api_jwt_token`) shared by monorepo services."
USER_BOUND_SCOPE_PREFIX = f"{SERVICE_SCOPE}:"
"Prefix of per-user `users:<innohassle_id>` scopes issued by `generate-service-token?only_for_me=true`."


@dataclass(frozen=True)
class ServiceCaller:
    innohassle_id: str | None
    "Owner of a per-user `users:<id>` token; None for a service token with the full `users` scope"


async def verify_service_token(
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> ServiceCaller:
    """
    Require an InNoHassle Accounts service JWT with the `users` scope or a per-user `users:<id>` scope.

    `users` is issued by admins via `/tokens/generate-service-token?scopes=users&only_for_me=false`. Any user can issue
    `users:<id>` for themselves, so endpoints about a person accept it only for its owner
    (`ServiceEmailAccessDep`).
    """
    if bearer is None or not bearer.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No credentials provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scopes = service_token_scopes(bearer.credentials) or []
    if SERVICE_SCOPE in scopes:
        return ServiceCaller(innohassle_id=None)
    owner_id = next(
        (scope.removeprefix(USER_BOUND_SCOPE_PREFIX) for scope in scopes if scope.startswith(USER_BOUND_SCOPE_PREFIX)),
        None,
    )
    if owner_id:
        return ServiceCaller(innohassle_id=owner_id)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid service token",
        headers={"WWW-Authenticate": "Bearer"},
    )


ServiceTokenDep = Annotated[ServiceCaller, Depends(verify_service_token)]


async def verify_service_email_access(email: str, caller: ServiceTokenDep) -> None:
    """Allow a per-user `users:<id>` token to read only data about its owner's own Innopolis email."""
    if caller.innohassle_id is None:
        return
    owner = await inh_accounts.get_user(innohassle_id=caller.innohassle_id)
    if owner is None or owner.innopolis_info.email.strip().casefold() != email.strip().casefold():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Per-user service token may access only its owner's data",
        )


ServiceEmailAccessDep = Annotated[None, Depends(verify_service_email_access)]


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
