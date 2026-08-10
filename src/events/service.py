"""Shared business logic: draft access, status, submission guardrails, conversions."""

import datetime as dtm
from typing import cast

from beanie import PydanticObjectId
from fastapi import HTTPException

from src.events.clubs_client import ClubInfo, clubs_client
from src.events.config import settings
from src.events.mongo import (
    Enrollment,
    EnrollmentType,
    Event,
    EventData,
    Host,
    HostType,
    Locale,
    ModerationStatus,
    SubmissionData,
    SubmissionLocale,
)
from src.events.schemas import DraftStatus, PublicHost, UserRoles
from src.inh_accounts_sdk import inh_accounts


def utcnow() -> dtm.datetime:
    return dtm.datetime.now(dtm.UTC)


def new_id() -> str:
    return str(PydanticObjectId())


def new_host_id() -> str:
    return new_id()


def new_link_id() -> str:
    return new_id()


def owned_club_ids(roles: UserRoles) -> set[str]:
    return {club.club_id for club in roles.clubs}


def can_view_draft(event: Event, roles: UserRoles) -> bool:
    if event.creator_id == roles.innohassle_id:
        return True
    owned = owned_club_ids(roles)
    if owned & set(event.invitations):
        return True
    return any(host.type == HostType.CLUB and host.club_id in owned for host in event.draft.data.hosts)


def can_edit_draft(event: Event, roles: UserRoles) -> bool:
    if event.creator_id == roles.innohassle_id:
        return True
    owned = owned_club_ids(roles)
    return any(host.type == HostType.CLUB and host.club_id in owned for host in event.draft.data.hosts)


def is_pending_invitee(event: Event, roles: UserRoles) -> bool:
    return bool(owned_club_ids(roles) & set(event.invitations))


async def get_viewable_draft(id: PydanticObjectId, roles: UserRoles, detail: str = "Draft not found") -> Event:
    event = await Event.get(id)
    if event is None or not can_view_draft(event, roles):
        raise HTTPException(status_code=404, detail=detail)
    return event


async def get_editable_draft(id: PydanticObjectId, roles: UserRoles, detail: str = "Draft not found") -> Event:
    event = await Event.get(id)
    if event is None or not can_edit_draft(event, roles):
        raise HTTPException(status_code=404, detail=detail)
    return event


def pick_event_name(locales: dict[str, Locale] | dict[str, SubmissionLocale]) -> str | None:
    """Pick event name using settings.locales priority, then any present locale."""
    for code in settings.locales:
        locale = locales.get(code)
        if locale is None:
            continue
        name = (locale.name or "").strip()
        if name:
            return name
    for locale in locales.values():
        name = (locale.name or "").strip()
        if name:
            return name
    return None


async def resolve_invited_by_name(creator_id: str) -> str:
    user = await inh_accounts.get_user(innohassle_id=creator_id)
    if user is None:
        return creator_id
    name = (user.innopolis_info.name or "").strip()
    if name:
        return name
    return user.innopolis_info.email


def draft_status(event: Event) -> DraftStatus | None:
    if event.public is not None and event.draft.revision == event.public.revision:
        return DraftStatus.PUBLISHED
    if event.submission is not None and event.draft.revision == event.submission.revision:
        if event.submission.moderation.status == ModerationStatus.APPROVED:
            return DraftStatus.UNPUBLISHED
        return DraftStatus(event.submission.moderation.status.value)
    return None


def eligibility_reasons(event: Event, roles: UserRoles) -> list[str]:
    del roles  # roles no longer gate host ownership at submit time
    reasons: list[str] = []
    for code, locale in event.draft.data.locales.items():
        name_empty = not (locale.name or "").strip()
        description_empty = not (locale.description or "").strip()
        if name_empty and description_empty:
            reasons.append(f"Description and name in {code} locale are empty")
        elif name_empty:
            reasons.append(f"Name in {code} locale is empty")
        elif description_empty:
            reasons.append(f"Description in {code} locale is empty")
    if not event.draft.data.hosts:
        reasons.append("Hosts are not set")
    if not (event.draft.data.location or "").strip():
        reasons.append("Location is empty")
    starts_at = event.draft.data.starts_at
    if starts_at is None:
        reasons.append("Event start time is not set")
    elif starts_at < utcnow():
        reasons.append("Event start time in the past")
    duration = event.draft.data.duration_hours
    if duration is None:
        reasons.append("Event duration is not set")
    elif duration <= 0:
        reasons.append("Event duration must be positive")
    enrollment = event.draft.data.enrollment
    if enrollment is None:
        reasons.append("Enrollment is not set")
    elif enrollment.type == EnrollmentType.EXTERNAL and not (enrollment.url or "").strip():
        reasons.append("External enrollment URL is empty")
    return reasons


def build_submission_data(data: EventData) -> SubmissionData:
    """Convert (validated) draft data into immutable submission data."""
    return SubmissionData(
        starts_at=cast(dtm.datetime, data.starts_at),
        image_id=data.image_id,
        location=cast(str, data.location),
        locales={
            code: SubmissionLocale(name=cast(str, locale.name), description=cast(str, locale.description))
            for code, locale in data.locales.items()
        },
        hosts=list(data.hosts),
        duration_hours=cast(float, data.duration_hours),
        enrollment=cast(Enrollment, data.enrollment),
        links=list(data.links),
    )


def to_public_host(host: Host, clubs: dict[str, ClubInfo]) -> PublicHost:
    """Map stored Host to the public display shape."""
    if host.type == HostType.EXTERNAL:
        return PublicHost(id=host.id, display_name=cast(str, host.name), link=host.url)
    club_id = cast(str, host.club_id)
    club = clubs.get(club_id)
    if club is None:
        raise HTTPException(status_code=502, detail=f"Club {club_id} not found in clubs service")
    return PublicHost(
        id=host.id,
        display_name=club.title,
        link=f"{settings.innohassle_url.rstrip('/')}/clubs/{club.slug}",
    )


def to_public_hosts(hosts: list[Host], clubs: dict[str, ClubInfo]) -> list[PublicHost]:
    return [to_public_host(host, clubs) for host in hosts]


async def load_clubs_for_hosts(hosts: list[Host]) -> dict[str, ClubInfo]:
    club_ids = {host.club_id for host in hosts if host.type == HostType.CLUB and host.club_id}
    return await clubs_client.get_clubs(club_ids)


async def resolve_public_hosts(hosts: list[Host]) -> list[PublicHost]:
    clubs = await load_clubs_for_hosts(hosts)
    return to_public_hosts(hosts, clubs)
