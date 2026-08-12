__all__ = [
    "AddClubHostBody",
    "AddExternalHostBody",
    "AddLinkBody",
    "CreateDraft",
    "DeclineBody",
    "DraftListItem",
    "DraftOut",
    "DraftStatus",
    "EventDataOut",
    "EventDataSummary",
    "EventListData",
    "EventListItem",
    "EventOut",
    "FeedbackBody",
    "ImageUploadResponse",
    "InviteClubBody",
    "MeOut",
    "OrderHostsBody",
    "OrderLinksBody",
    "OwnedClub",
    "PatchDraft",
    "PatchExternalHostBody",
    "PatchLinkBody",
    "PublicHost",
    "PutLocale",
    "RestoreBody",
    "RestoreSource",
    "RestoreSourceItem",
    "SubmissionDataSummary",
    "SubmissionListItem",
    "SubmissionOut",
    "SubmissionSummary",
    "UserRoles",
]

import datetime as dtm
from enum import StrEnum
from typing import Literal

from beanie import PydanticObjectId
from pydantic import Field

from src.common_pydantic import BaseSchema
from src.events.mongo import Enrollment, EventData, EventLink, Host, Moderation, Submission, SubmissionLocale
from src.events.time_utils import TZAwareDateTime


class OwnedClub(BaseSchema):
    club_id: str
    "ID of the club"
    title: str
    "Display name of the club"


class UserRoles(BaseSchema):
    innohassle_id: str
    is_club_leader: bool
    is_event_manager: bool
    is_moderator: bool
    clubs: list[OwnedClub]
    "Clubs owned by the user"


class MeOut(BaseSchema):
    roles: list[str]
    'List of roles: "club-leader", "event-manager", "moderator"'
    clubs: list[OwnedClub]


class CreateDraft(BaseSchema):
    starts_at: TZAwareDateTime | None = None
    location: str | None = None
    locales: list[str] | None = None
    "Locale codes to pre-create in the draft"
    duration_hours: float | None = None
    enrollment: Enrollment | None = None


class PatchDraft(BaseSchema):
    starts_at: TZAwareDateTime | None = None
    location: str | None = None
    duration_hours: float | None = None
    enrollment: Enrollment | None = None


class AddLinkBody(BaseSchema):
    url: str
    name: str | None = None


class PatchLinkBody(BaseSchema):
    url: str | None = None
    name: str | None = None


class PutLocale(BaseSchema):
    name: str | None
    "Locale name; null or empty string allowed"
    description: str | None
    "Locale description; null or empty string allowed"


class AddExternalHostBody(BaseSchema):
    name: str
    url: str | None = None


class PatchExternalHostBody(BaseSchema):
    name: str | None = None
    url: str | None = None


class AddClubHostBody(BaseSchema):
    club_id: str


class InviteClubBody(BaseSchema):
    club_id: str


class OrderHostsBody(BaseSchema):
    host_ids: list[str]


class OrderLinksBody(BaseSchema):
    link_ids: list[str]


class RestoreBody(BaseSchema):
    source: Literal["submission", "public"] = Field(alias="from")


class RestoreSource(StrEnum):
    SUBMISSION = "submission"
    PUBLIC = "public"


class RestoreSourceItem(BaseSchema):
    entity: RestoreSource
    revision: dtm.datetime


class FeedbackBody(BaseSchema):
    feedback: str = ""
    "Moderation feedback (may be empty)"


class DeclineBody(BaseSchema):
    feedback: str
    "Moderation feedback (required)"


class ImageUploadResponse(BaseSchema):
    image_id: str
    "File ID of the uploaded event image"


class DraftStatus(StrEnum):
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    PENDING = "pending"
    DECLINED = "declined"


class DraftOut(BaseSchema):
    id: PydanticObjectId
    creator_id: str
    status: DraftStatus | None
    has_public: bool
    "Whether a published copy exists (blocks draft deletion until unpublished)"
    can_be_restored_from: list[RestoreSourceItem]
    "Sources whose revision differs from the draft; entities match POST /drafts/:id/restore `from`"
    revision: dtm.datetime
    data: EventData
    invitations: list[str]
    "Club ids with pending host invitations"
    can_edit: bool
    "Whether the current user can edit this draft"
    can_submit: bool
    "Whether the draft can be submitted"
    cannot_submit_reasons: list[str]
    "Human-readable reasons why the draft cannot be submitted"
    feedback: str | None = None
    "Latest moderation feedback when set; kept after the draft diverges from the submission"


class EventDataSummary(BaseSchema):
    starts_at: dtm.datetime | None = None
    image_id: str | None = None
    location: str | None = None
    name: str | None = None
    "Display name picked from locales by settings.locales priority"
    hosts: list[Host] = Field(default_factory=list)
    duration_hours: float | None = None
    enrollment: Enrollment | None = None


class SubmissionDataSummary(BaseSchema):
    starts_at: dtm.datetime
    image_id: str | None = None
    location: str
    name: str | None = None
    "Display name picked from locales by settings.locales priority"
    hosts: list[Host]
    duration_hours: float
    enrollment: Enrollment


class PublicHost(BaseSchema):
    """Host as shown on published events (resolved for display)."""

    id: str
    display_name: str
    link: str | None = None


class EventDataOut(BaseSchema):
    starts_at: dtm.datetime
    image_id: str | None = None
    location: str
    locales: dict[str, SubmissionLocale]
    hosts: list[PublicHost]
    duration_hours: float
    enrollment: Enrollment
    links: list[EventLink] = Field(default_factory=list)


class EventListData(BaseSchema):
    starts_at: dtm.datetime
    image_id: str | None = None
    location: str
    name: str | None = None
    "Display name picked from locales by settings.locales priority"
    hosts: list[PublicHost]
    duration_hours: float
    enrollment: Enrollment


class DraftListItem(BaseSchema):
    id: PydanticObjectId
    creator_id: str
    status: DraftStatus | None
    revision: dtm.datetime
    data: EventDataSummary
    invited_by: str | None = None
    "Present only while the current user's club has a pending invitation"


class SubmissionOut(BaseSchema):
    id: PydanticObjectId
    creator_id: str
    status: DraftStatus | None
    "Same lifecycle statuses as drafts; `unpublished` when approved but public was removed"
    submission: Submission


class SubmissionSummary(BaseSchema):
    revision: dtm.datetime
    submitted_at: dtm.datetime
    moderation: Moderation
    data: SubmissionDataSummary


class SubmissionListItem(BaseSchema):
    id: PydanticObjectId
    creator_id: str
    status: DraftStatus | None
    "Same lifecycle statuses as submission detail"
    submission: SubmissionSummary


class EventOut(BaseSchema):
    id: PydanticObjectId
    creator_id: str
    data: EventDataOut
    enrolled_count: int
    enrolled: bool | None = None
    "Visible to authenticated users only"
    enrolled_emails: list[str] | None = None
    "Visible to the author or a moderator only"
    revision: dtm.datetime | None = None
    "Visible to the author or a moderator only"
    approved_at: dtm.datetime | None = None
    "Visible to the author or a moderator only"
    approved_by: str | None = None
    "Visible to a moderator only"
    can_edit_draft: bool = False
    "Whether the current user can edit the underlying draft (same rules as draft can_edit)"


class EventListItem(BaseSchema):
    id: PydanticObjectId
    creator_id: str
    data: EventListData
    enrolled_count: int
    enrolled: bool | None = None
    "Visible to authenticated users only"
    revision: dtm.datetime | None = None
    "Visible to the author or a moderator only"
    approved_at: dtm.datetime | None = None
    "Visible to the author or a moderator only"
    approved_by: str | None = None
    "Visible to a moderator only"
