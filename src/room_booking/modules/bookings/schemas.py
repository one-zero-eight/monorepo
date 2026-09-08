import datetime as dtm
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from src.room_booking.modules.bookings.recurrence import RecurrencePattern
from src.room_booking.modules.bookings.tz_utils import MSKDatetime

type BookingStatus = Literal["Accept", "Tentative", "Decline", "Unknown", "NoResponseReceived"]
type Presence = Literal["present", "absent", "unknown"]


class Attendee(BaseModel):
    email: str
    "Email of the attendee"
    status: BookingStatus | None
    "Response status of the attendee"
    assosiated_room_id: str | None
    "If attendee is a room, ID of the room they are associated with, otherwise None"


class Booking(BaseModel):
    room_id: str
    "ID of the room"
    start: MSKDatetime
    "Start time of booking"
    end: MSKDatetime
    "End time of booking"
    title: str
    "Title of the booking"
    outlook_booking_id: str | None
    "ID of outlook booking in service account calendar. Only set if we can manage the booking."
    outlook_entry_id: str | None
    "Hex Entry Id returned by Outlook's free busy info. Only set if we cannot manage the booking."
    attendees: list[Attendee] | None
    "List of attendees of the booking"
    operation_id: str | None = None
    uid: str | None = None
    organizer_mailbox: str | None = None
    room_response: BookingStatus | None = None
    room_presence: Presence = "unknown"
    checked_at: dtm.datetime | None = None
    message_body: str | None = None
    busy_type: str | None = None
    source: Literal["organizer", "room", "free_busy"] = "organizer"
    source_item_id: str | None = None
    change_key: str | None = None
    categories: list[str] | None = None
    "Outlook categories on the calendar item"
    recurrence: str | None = None
    "EWS Recurrence XML when the calendar item is a recurring master"
    related_to_me: bool | None = None
    """
    Whether the booking is related to the user, so he can delete, update it or not.
    If None we don't know whether it is related to the user or not.
    """

    @computed_field
    @property
    def id(self) -> str:
        "Source-scoped identity, including the occurrence window. Never merge by slot alone."
        identity = self.uid or self.outlook_booking_id or self.outlook_entry_id or self.source_item_id
        if identity is None:
            identity = sha256(f"{self.title}:{self.busy_type}:{self.attendees}".encode()).hexdigest()[:24]
        return (
            f"{self.source}:{self.organizer_mailbox or ''}:{identity}:"
            f"{self.room_id}-{round(self.start.timestamp())}-{round(self.end.timestamp())}"
        )


class CreateBookingRequest(BaseModel):
    operation_id: str | None = Field(default=None, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:-]+$")
    room_id: str
    "ID of the room to book"
    title: str
    "Title of the booking"
    start: MSKDatetime
    "Start time of the booking"
    end: MSKDatetime
    "End time of the booking"
    participant_emails: list[str] | None
    "List of participant emails to invite to the booking"
    recurrence: RecurrencePattern | None = None
    "Optional recurrence pattern"
    categories: list[str] | None = None
    "Optional Outlook categories"
    description: str | None = None
    "Optional text appended to the calendar item body after the standard notice"


class PatchBookingRequest(BaseModel):
    title: str | None
    "New title of the booking"
    start: MSKDatetime | None
    "New start time of the booking"
    end: MSKDatetime | None
    "New end time of the booking"


class ReconcileBookingEntry(BaseModel):
    operation_id: str | None = None
    outlook_booking_id: str | None = None
    uid: str | None = None
    organizer_mailbox: str | None = None
    room_id: str
    start: MSKDatetime | None = None
    end: MSKDatetime | None = None
    scope: Literal["series", "occurrence"] = "series"


class ReconcileBookingResult(BaseModel):
    operation_id: str | None = None
    outlook_booking_id: str | None = None
    uid: str | None = None
    organizer_mailbox: str | None = None
    room_id: str
    status: Literal["ok", "error"] = "ok"
    organizer_presence: Presence = "unknown"
    room_presence: Presence = "unknown"
    room_response: BookingStatus | None = None
    checked_at: dtm.datetime
    message_body: str | None = None
    booking: Booking | None = None
    evidence: list[str] = Field(default_factory=list)
    error: str | None = None
    cancellation_status: Literal["cancelling", "cancelled", "requires_review"] | None = None


class ScopedCancelBookingRequest(ReconcileBookingEntry):
    scope: Literal["series", "occurrence"]


class CancelExtraBookingRequest(BaseModel):
    room_id: str
    start: MSKDatetime
    end: MSKDatetime
    title: str
    outlook_booking_id: str | None = None
    outlook_entry_id: str | None = None
