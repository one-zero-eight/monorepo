import datetime as dtm
from enum import StrEnum

from beanie import PydanticObjectId
from pydantic import BaseModel, field_validator, model_validator

from src.common_pydantic import BaseSchema


def normalize_datetime(v: dtm.datetime) -> dtm.datetime:
    if v.tzinfo is None or v.utcoffset() is None:
        raise ValueError("Datetime must include timezone")
    return v.replace(microsecond=0)


def parse_timezone_datetime(v: dtm.datetime | str) -> dtm.datetime:
    if isinstance(v, str):
        v = dtm.datetime.fromisoformat(v)
    return normalize_datetime(v)


def normalize_datetime_string(v: dtm.datetime | str) -> str:
    normalized = parse_timezone_datetime(v)
    value = normalized.isoformat()
    if normalized.utcoffset() == dtm.timedelta(0):
        return value.replace("+00:00", "Z")
    return value


def _normalize_datetimes(values: list[dtm.datetime]) -> list[dtm.datetime]:
    return [normalize_datetime(value) for value in values]


def _normalize_sorted_datetimes(values: list[dtm.datetime]) -> list[dtm.datetime]:
    return sorted(_normalize_datetimes(values))


class TimeRange(BaseSchema):
    start: str
    end: str


class MeetingTime(BaseSchema):
    start: str
    "Selected meeting start time"
    end: str
    "Selected meeting end time"

    @field_validator("start", "end", mode="before")
    @classmethod
    def normalize_time(cls, v: dtm.datetime | str) -> str:
        return normalize_datetime_string(v)

    @model_validator(mode="after")
    def validate_time_order(self) -> MeetingTime:
        if self.end_datetime <= self.start_datetime:
            raise ValueError("Meeting end time must be after start time")
        return self

    @property
    def start_datetime(self) -> dtm.datetime:
        return parse_timezone_datetime(self.start)

    @property
    def end_datetime(self) -> dtm.datetime:
        return parse_timezone_datetime(self.end)


class MeetingStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class BookedRoom(BaseSchema):
    room_id: str
    "Booked room ID"
    outlook_booking_id: str | None = None
    "Room Booking service booking ID"
    outlook_entry_id: str | None = None
    "Outlook entry ID"


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
        if not v:
            raise ValueError("Meeting must have at least one slot")
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
        if not v:
            raise ValueError("Meeting must have at least one slot")
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
    booked_room: BookedRoom | None = None
    "Booked room reference"
    archive_after: dtm.datetime
    "Time after which the meeting is automatically archived"
    is_archived: bool
    "Whether the meeting is archived"
    archived_at: dtm.datetime | None = None
    "Effective automatic or manual archive time"


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
    archive_after: dtm.datetime
    "Time after which the meeting is automatically archived"
    is_archived: bool
    "Whether the meeting is archived"
    archived_at: dtm.datetime | None = None
    "Effective automatic or manual archive time"


class AvailableRoom(BaseSchema):
    id: str
    "Room ID"
    name: str
    "Room name"
    capacity: int | None = None
    "Room capacity"
    location: str
    "Room location label"


class BookRoomRequest(BaseSchema):
    room_id: str
    "Room ID to book"


class RoomBookingRoom(BaseModel):
    id: str
    title: str
    short_name: str
    capacity: int | None = None


class RoomBookingBooking(BaseModel):
    room_id: str
    start: dtm.datetime
    end: dtm.datetime


class RoomBookingCanBook(BaseModel):
    can_book: bool
    reason_why_cannot: str = ""


class RoomBookingCreatedBooking(BaseModel):
    room_id: str
    outlook_booking_id: str | None
    outlook_entry_id: str | None
