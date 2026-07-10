import datetime as dtm

from beanie import PydanticObjectId
from pydantic import field_validator, model_validator

from src.common_pydantic import BaseSchema


def normalize_datetime(v: dtm.datetime) -> dtm.datetime:
    if v.tzinfo is None:
        v = v.replace(tzinfo=dtm.UTC)
    else:
        v = v.astimezone(dtm.UTC)
    return v.replace(microsecond=0)


def _normalize_datetimes(values: list[dtm.datetime]) -> list[dtm.datetime]:
    return [normalize_datetime(value) for value in values]


def _normalize_sorted_datetimes(values: list[dtm.datetime]) -> list[dtm.datetime]:
    return sorted(_normalize_datetimes(values))


class TimeRange(BaseSchema):
    start: str
    end: str


class MeetingTime(BaseSchema):
    start: dtm.datetime
    "Selected meeting start time"
    end: dtm.datetime
    "Selected meeting end time"

    @model_validator(mode="after")
    def validate_time_order(self) -> MeetingTime:
        self.start = normalize_datetime(self.start)
        self.end = normalize_datetime(self.end)
        if self.end <= self.start:
            raise ValueError("Meeting end time must be after start time")
        return self


class EventCreate(BaseSchema):
    name: str
    "Name of the event"
    description: str | None = None
    "Description of the event"
    slots: list[dtm.datetime]
    "All possible slots for the event"
    timezone: str = "UTC"
    "IANA timezone name"
    specific_time: bool = False
    "Whether the event has specific time slots"
    time_range: TimeRange | None = None
    "Optional metadata for display/edit"

    @field_validator("slots", mode="after")
    @classmethod
    def validate_slots(cls, v: list[dtm.datetime]) -> list[dtm.datetime]:
        return _normalize_sorted_datetimes(v)


class EventUpdate(BaseSchema):
    name: str | None = None
    "Name of the event"
    description: str | None = None
    "Description of the event"
    slots: list[dtm.datetime] | None = None
    "All possible slots for the event"
    timezone: str | None = None
    "IANA timezone name"
    specific_time: bool | None = None
    "Whether the event has specific time slots"
    time_range: TimeRange | None = None
    "Optional metadata for display/edit"
    selected_time: MeetingTime | None = None
    "Final selected meeting time"

    @field_validator("slots", mode="after")
    @classmethod
    def validate_slots(cls, v: list[dtm.datetime] | None) -> list[dtm.datetime] | None:
        if v is None:
            return None
        return _normalize_sorted_datetimes(v)


class ParticipantUpdate(BaseSchema):
    availability: list[dtm.datetime]
    "List of slots the participant is available for"

    @field_validator("availability", mode="after")
    @classmethod
    def validate_slots(cls, v: list[dtm.datetime]) -> list[dtm.datetime]:
        return _normalize_datetimes(v)


class ParticipantView(BaseSchema):
    user_id: str
    "InNoHassle Accounts user ID"
    email: str | None = None
    "Innopolis email"
    name: str | None = None
    "Full name of the participant"
    telegram: str | None = None
    "Telegram @username if linked"
    availability: list[dtm.datetime]
    "List of slots the participant is available for"


class EventView(BaseSchema):
    id: PydanticObjectId
    "Event ID"
    slug: str
    "Short URL-safe public event reference"
    name: str
    "Name of the event"
    description: str | None = None
    "Description of the event"
    slots: list[dtm.datetime]
    "All possible slots for the event"
    participants: list[ParticipantView]
    "Participants with profile data and availability"
    created_at: dtm.datetime
    "Time when the event was created"
    timezone: str = "UTC"
    "IANA timezone name"
    owner_id: str | None = None
    "ID of the user who created the event"
    specific_time: bool = False
    "Whether the event has specific time slots"
    time_range: TimeRange | None = None
    "Optional metadata for display/edit"
    selected_time: MeetingTime | None = None
    "Final selected meeting time"


class EventSummary(BaseSchema):
    id: PydanticObjectId
    "Event ID"
    slug: str
    "Short URL-safe public event reference"
    name: str
    "Name of the event"
    description: str | None = None
    "Description of the event"
    created_at: dtm.datetime
    "Time when the event was created"
    participants_count: int
    "Number of participants in the event"
    date_range_label: str | None = None
    "Optional; frontend can derive from slots"
    selected_time: MeetingTime | None = None
    "Final selected meeting time"
