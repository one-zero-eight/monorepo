__all__ = [
    "Draft",
    "Enrollment",
    "EnrollmentType",
    "Event",
    "EventData",
    "EventLink",
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
    id: str
    "Stable host id within the event"
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


class EnrollmentType(StrEnum):
    EXTERNAL = "external"
    INTERNAL = "internal"


class Enrollment(BaseSchema):
    type: EnrollmentType
    url: str | None = None
    "Enrollment URL (required for external)"
    capacity: int | None = None
    "Max enrollments for internal; null means unlimited"

    @model_validator(mode="after")
    def validate_fields(self) -> Enrollment:
        if self.type == EnrollmentType.EXTERNAL and not (self.url or "").strip():
            raise ValueError("url is required for external enrollment")
        if self.type == EnrollmentType.INTERNAL and self.url is not None:
            raise ValueError("url is only allowed for external enrollment")
        if self.type == EnrollmentType.EXTERNAL and self.capacity is not None:
            raise ValueError("capacity is only allowed for internal enrollment")
        if self.capacity is not None and self.capacity < 1:
            raise ValueError("capacity must be at least 1")
        return self


class EventLink(BaseSchema):
    id: str
    "Stable link id within the event"
    url: str
    name: str | None = None


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
    hosts: list[Host] = Field(default_factory=list)
    "Event hosts"
    duration_hours: float | None = None
    "Event duration in hours"
    enrollment: Enrollment | None = None
    "Enrollment configuration"
    links: list[EventLink] = Field(default_factory=list)
    "Related links"


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
    hosts: list[Host]
    "Event hosts"
    duration_hours: float
    "Event duration in hours"
    enrollment: Enrollment
    "Enrollment configuration"
    links: list[EventLink] = Field(default_factory=list)
    "Related links"


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
    enrolled_emails: list[str] = Field(default_factory=list)
    "Emails of users enrolled in the event"
    data: SubmissionData


class Event(BeanieDocument):
    """One MongoDB document holding draft, submission, and public stages."""

    creator_id: str
    "InNoHassle Accounts id of the author"
    invitations: list[str] = Field(default_factory=list)
    "Club ids invited as hosts (pending)"
    draft: Draft
    submission: Submission | None = None
    public: PublicEvent | None = None


document_models = [Event]
