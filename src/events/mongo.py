__all__ = [
    "Draft",
    "Event",
    "EventData",
    "Host",
    "HostType",
    "Locale",
    "Moderation",
    "ModerationStatus",
    "PublicEvent",
    "Submission",
    "SubmissionData",
    "SubmissionLocale",
    "document_models",
]

import datetime as dtm
from enum import StrEnum

from pydantic import Field, model_validator

from src.common_beanie import BeanieDocument
from src.common_pydantic import BaseSchema


class HostType(StrEnum):
    CLUB = "club"
    EXTERNAL = "external"


class Host(BaseSchema):
    type: HostType
    "Host type"
    club_id: str | None = None
    "Club id (for type=club)"
    name: str | None = None
    "External host name (for type=external)"
    url: str | None = None
    "External host url (for type=external, optional)"

    @model_validator(mode="after")
    def validate_fields(self) -> Host:
        if self.type == HostType.CLUB and not self.club_id:
            raise ValueError("club_id is required for a club host")
        if self.type == HostType.EXTERNAL and not self.name:
            raise ValueError("name is required for an external host")
        return self


class Locale(BaseSchema):
    """Locale content in a draft — all fields optional."""

    name: str | None = None
    description: str | None = None


class SubmissionLocale(BaseSchema):
    """Locale content in a submission/public event — fields are required."""

    name: str
    description: str


class EventData(BaseSchema):
    """Mutable draft data; all fields may be unset until submission."""

    starts_at: dtm.datetime | None = None
    "Event start time, normalized to UTC"
    image_id: str | None = None
    "ID of the event image in MinIO"
    location: str | None = None
    "Event location"
    locales: dict[str, Locale] = Field(default_factory=dict)
    "Localized title and description"
    host: Host | None = None
    "Event host"


class SubmissionData(BaseSchema):
    """Immutable data of a submission/public event; only image_id is nullable."""

    starts_at: dtm.datetime
    "Event start time, normalized to UTC"
    image_id: str | None = None
    "ID of the event image in MinIO"
    location: str
    "Event location"
    locales: dict[str, SubmissionLocale]
    "Localized title and description"
    host: Host
    "Event host"


class Draft(BaseSchema):
    revision: dtm.datetime
    "Last update time of the draft"
    data: EventData


class ModerationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"


class Moderation(BaseSchema):
    status: ModerationStatus
    feedback: str | None = None
    updated_at: dtm.datetime
    "Timestamp of the last moderation action (submit, approve, or decline)"


class Submission(BaseSchema):
    revision: dtm.datetime
    "Draft revision that was submitted"
    submitted_at: dtm.datetime
    moderation: Moderation
    data: SubmissionData


class PublicEvent(BaseSchema):
    revision: dtm.datetime
    "Draft revision that was approved"
    submitted_at: dtm.datetime
    approved_by: str
    "Email of the moderator who approved the event"
    approved_at: dtm.datetime
    enrolled_users: list[str] = Field(default_factory=list)
    "Users who checked in on the event"
    data: SubmissionData


class Event(BeanieDocument):
    """One MongoDB document holding draft, submission, and public stages."""

    creator_id: str
    "InNoHassle Accounts id of the author"
    draft: Draft
    submission: Submission | None = None
    public: PublicEvent | None = None


document_models = [Event]
