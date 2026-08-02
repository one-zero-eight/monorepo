__all__ = [
    "CreateDraft",
    "DeclineBody",
    "DraftListItem",
    "DraftOut",
    "DraftStatus",
    "Eligibility",
    "EventDataSummary",
    "EventListItem",
    "EventOut",
    "FeedbackBody",
    "ImageUploadResponse",
    "LocaleSummary",
    "MeOut",
    "OwnedClub",
    "PatchDraft",
    "PatchLocale",
    "RestoreBody",
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
from src.events.mongo import EventData, Host, Moderation, Submission, SubmissionData
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
    host: Host | None = None


class PatchDraft(BaseSchema):
    starts_at: TZAwareDateTime | None = None
    location: str | None = None
    host: Host | None = None


class PatchLocale(BaseSchema):
    name: str | None = None
    description: str | None = None


class RestoreBody(BaseSchema):
    source: Literal["submission", "public"] = Field(alias="from")


class FeedbackBody(BaseSchema):
    feedback: str = ""
    "Moderation feedback (may be empty)"


class DeclineBody(BaseSchema):
    feedback: str
    "Moderation feedback (required)"


class ImageUploadResponse(BaseSchema):
    image_id: str
    "File ID of the uploaded event image"


class Eligibility(BaseSchema):
    eligible: bool
    why: list[str]
    "Human-readable reasons why the draft cannot be submitted"


class DraftStatus(StrEnum):
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"
    PENDING = "pending"
    DECLINED = "declined"


class DraftOut(BaseSchema):
    id: PydanticObjectId
    creator_id: str
    status: DraftStatus | None
    revision: dtm.datetime
    data: EventData


class LocaleSummary(BaseSchema):
    name: str | None = None
    "Description is omitted in list responses"


class EventDataSummary(BaseSchema):
    starts_at: dtm.datetime | None = None
    image_id: str | None = None
    location: str | None = None
    locales: dict[str, LocaleSummary] = Field(default_factory=dict)
    host: Host | None = None


class SubmissionDataSummary(BaseSchema):
    starts_at: dtm.datetime
    image_id: str | None = None
    location: str
    locales: dict[str, LocaleSummary]
    host: Host


class DraftListItem(BaseSchema):
    id: PydanticObjectId
    creator_id: str
    status: DraftStatus | None
    revision: dtm.datetime
    data: EventDataSummary


class SubmissionOut(BaseSchema):
    id: PydanticObjectId
    creator_id: str
    submission: Submission


class SubmissionSummary(BaseSchema):
    revision: dtm.datetime
    submitted_at: dtm.datetime
    moderation: Moderation
    data: SubmissionDataSummary


class SubmissionListItem(BaseSchema):
    id: PydanticObjectId
    creator_id: str
    submission: SubmissionSummary


class EventOut(BaseSchema):
    id: PydanticObjectId
    creator_id: str
    data: SubmissionData
    enrolled_count: int
    enrolled: bool | None = None
    "Visible to authenticated users only"
    enrolled_users: list[str] | None = None
    "Visible to the author or a moderator only"
    revision: dtm.datetime | None = None
    "Visible to the author or a moderator only"
    approved_at: dtm.datetime | None = None
    "Visible to the author or a moderator only"
    approved_by: str | None = None
    "Visible to a moderator only"


class EventListItem(BaseSchema):
    id: PydanticObjectId
    creator_id: str
    data: SubmissionDataSummary
    enrolled_count: int
    enrolled: bool | None = None
    "Visible to authenticated users only"
    revision: dtm.datetime | None = None
    "Visible to the author or a moderator only"
    approved_at: dtm.datetime | None = None
    "Visible to the author or a moderator only"
    approved_by: str | None = None
    "Visible to a moderator only"
