"""Response builders with per-role visibility rules."""

from src.events.config import settings
from src.events.mongo import Event, EventData, PublicEvent, Submission, SubmissionData
from src.events.schemas import (
    DraftListItem,
    DraftOut,
    EventDataOut,
    EventDataSummary,
    EventListData,
    EventListItem,
    EventOut,
    PublicHost,
    SubmissionDataSummary,
    SubmissionListItem,
    SubmissionOut,
    SubmissionSummary,
    UserRoles,
)
from src.events.service import draft_status, eligibility_reasons, pick_event_name
from src.inh_accounts_sdk import UserTokenData


def _summarize_draft_data(data: EventData) -> EventDataSummary:
    return EventDataSummary(
        starts_at=data.starts_at,
        image_id=data.image_id,
        location=data.location,
        name=pick_event_name(data.locales),
        host=data.host,
    )


def _summarize_submission_data(data: SubmissionData) -> SubmissionDataSummary:
    return SubmissionDataSummary(
        starts_at=data.starts_at,
        image_id=data.image_id,
        location=data.location,
        name=pick_event_name(data.locales),
        host=data.host,
    )


def _event_data_out(data: SubmissionData, host: PublicHost) -> EventDataOut:
    return EventDataOut(
        starts_at=data.starts_at,
        image_id=data.image_id,
        location=data.location,
        locales=data.locales,
        host=host,
    )


def _event_list_data(data: SubmissionData, host: PublicHost) -> EventListData:
    return EventListData(
        starts_at=data.starts_at,
        image_id=data.image_id,
        location=data.location,
        name=pick_event_name(data.locales),
        host=host,
    )


def build_draft_out(event: Event, roles: UserRoles) -> DraftOut:
    reasons = eligibility_reasons(event, roles)
    return DraftOut(
        id=event.id,
        creator_id=event.creator_id,
        status=draft_status(event),
        revision=event.draft.revision,
        data=event.draft.data,
        can_submit=not reasons,
        cannot_submit_reasons=reasons,
    )


def build_draft_list_item(event: Event) -> DraftListItem:
    return DraftListItem(
        id=event.id,
        creator_id=event.creator_id,
        status=draft_status(event),
        revision=event.draft.revision,
        data=_summarize_draft_data(event.draft.data),
    )


def build_submission_out(event: Event, submission: Submission) -> SubmissionOut:
    return SubmissionOut(
        id=event.id,
        creator_id=event.creator_id,
        submission=submission,
    )


def build_submission_list_item(event: Event, submission: Submission) -> SubmissionListItem:
    return SubmissionListItem(
        id=event.id,
        creator_id=event.creator_id,
        submission=SubmissionSummary(
            revision=submission.revision,
            submitted_at=submission.submitted_at,
            moderation=submission.moderation,
            data=_summarize_submission_data(submission.data),
        ),
    )


def _is_moderator(auth: UserTokenData | None) -> bool:
    return auth is not None and auth.email in settings.moderator_emails


def _is_author(event: Event, auth: UserTokenData | None) -> bool:
    return auth is not None and auth.innohassle_id == event.creator_id


def build_event_out(event: Event, public: PublicEvent, auth: UserTokenData | None, host: PublicHost) -> EventOut:
    out = EventOut(
        id=event.id,
        creator_id=event.creator_id,
        data=_event_data_out(public.data, host),
        enrolled_count=len(public.enrolled_users),
    )
    if auth is not None:
        out.enrolled = auth.innohassle_id in public.enrolled_users
    if _is_author(event, auth) or _is_moderator(auth):
        out.enrolled_users = list(public.enrolled_users)
        out.revision = public.revision
        out.approved_at = public.approved_at
    if _is_moderator(auth):
        out.approved_by = public.approved_by
    return out


def build_event_list_item(
    event: Event, public: PublicEvent, auth: UserTokenData | None, host: PublicHost
) -> EventListItem:
    item = EventListItem(
        id=event.id,
        creator_id=event.creator_id,
        data=_event_list_data(public.data, host),
        enrolled_count=len(public.enrolled_users),
    )
    if auth is not None:
        item.enrolled = auth.innohassle_id in public.enrolled_users
    if _is_author(event, auth) or _is_moderator(auth):
        item.revision = public.revision
        item.approved_at = public.approved_at
    if _is_moderator(auth):
        item.approved_by = public.approved_by
    return item
