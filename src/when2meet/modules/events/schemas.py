import datetime as dtm

from beanie import PydanticObjectId
from pydantic import field_validator

from src.common_pydantic import BaseSchema


def normalize_datetime(v: dtm.datetime) -> dtm.datetime:
    if v.tzinfo is None:
        v = v.replace(tzinfo=dtm.UTC)
    else:
        v = v.astimezone(dtm.UTC)
    return v.replace(microsecond=0)


class TimeRange(BaseSchema):
    start: str
    end: str


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
        return sorted([normalize_datetime(x) for x in v])


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

    @field_validator("slots", mode="after")
    @classmethod
    def validate_slots(cls, v: list[dtm.datetime] | None) -> list[dtm.datetime] | None:
        if v is None:
            return None
        return sorted([normalize_datetime(x) for x in v])


class ParticipantUpdate(BaseSchema):
    name: str
    "Name of the participant"
    availability: list[dtm.datetime]
    "List of slots the participant is available for"
    if_needed: list[dtm.datetime] | None = None
    "List of slots the participant is available for if needed"

    @field_validator("availability", "if_needed", mode="after")
    @classmethod
    def validate_slots(cls, v: list[dtm.datetime] | None) -> list[dtm.datetime] | None:
        if v is None:
            return None
        return [normalize_datetime(x) for x in v]


class EventSummary(BaseSchema):
    id: PydanticObjectId
    "Event ID"
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
