from typing import Literal

from pydantic import BaseModel, computed_field

from src.room_booking.modules.bookings.recurrence import RecurrencePattern
from src.room_booking.modules.bookings.tz_utils import MSKDatetime

type BookingStatus = Literal["Accept", "Tentative", "Decline", "Unknown"]


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
        "ID of the booking, computed from room_id, start and end"
        return f"{self.room_id}-{round(self.start.timestamp())}-{round(self.end.timestamp())}"


class CreateBookingRequest(BaseModel):
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


class CancelExtraBookingRequest(BaseModel):
    room_id: str
    start: MSKDatetime
    end: MSKDatetime
    title: str
    outlook_booking_id: str | None = None
    outlook_entry_id: str | None = None
