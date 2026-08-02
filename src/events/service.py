"""Shared business logic: draft status, submission guardrails, conversions."""

import datetime as dtm
from typing import cast

from beanie import PydanticObjectId
from fastapi import HTTPException

from src.events.mongo import (
    Event,
    EventData,
    Host,
    HostType,
    ModerationStatus,
    SubmissionData,
    SubmissionLocale,
)
from src.events.schemas import DraftStatus, UserRoles


def utcnow() -> dtm.datetime:
    return dtm.datetime.now(dtm.UTC)


async def get_own_draft(id: PydanticObjectId, innohassle_id: str, detail: str = "Draft not found") -> Event:
    event = await Event.get(id)
    if event is None or event.creator_id != innohassle_id:
        raise HTTPException(status_code=404, detail=detail)
    return event


def draft_status(event: Event) -> DraftStatus | None:
    if event.public is not None and event.draft.revision == event.public.revision:
        return DraftStatus.PUBLISHED
    if event.submission is not None and event.draft.revision == event.submission.revision:
        if event.submission.moderation.status == ModerationStatus.APPROVED:
            return DraftStatus.UNPUBLISHED
        return DraftStatus(event.submission.moderation.status.value)
    return None


def host_policy_reasons(host: Host, roles: UserRoles) -> list[str]:
    if host.type == HostType.CLUB:
        if not roles.is_club_leader:
            return ["Only club leaders can use a club as a host"]
        if host.club_id not in {club.club_id for club in roles.clubs}:
            return ["You are not a leader of the specified club"]
    if host.type == HostType.EXTERNAL and not roles.is_event_manager:
        return ["Only event managers can use an external host"]
    return []


def eligibility_reasons(event: Event, roles: UserRoles) -> list[str]:
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
    host = event.draft.data.host
    if host is None:
        reasons.append("Host is not set")
    else:
        reasons.extend(host_policy_reasons(host, roles))
    starts_at = event.draft.data.starts_at
    if starts_at is None:
        reasons.append("Event start time is not set")
    elif starts_at < utcnow():
        reasons.append("Event start time in the past")
    return reasons


async def assert_host_allowed(host: Host | None, roles: UserRoles) -> None:
    """Validate the host against role policies; raises 400 on violation."""
    if host is None:
        return
    reasons = host_policy_reasons(host, roles)
    if reasons:
        raise HTTPException(status_code=400, detail="; ".join(reasons))


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
        host=cast(Host, data.host),
    )
