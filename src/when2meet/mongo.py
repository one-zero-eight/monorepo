__all__ = ["Event", "Participant", "document_models"]
import datetime as dtm
from typing import Any, ClassVar

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from src.common_beanie import BeanieDocumentMixin
from src.common_pydantic import BaseSchema
from src.when2meet.modules.events.schemas import BookedRoom, MeetingTime, TimeRange


class Participant(BaseSchema):
    user_id: str
    "InNoHassle Accounts user ID"
    availability: list[dtm.datetime]
    "List of slots the participant is available for"


class Event(BeanieDocumentMixin, Document):
    name: str
    "Name of the event"
    description: str | None = None
    "Description of the event"
    slug: str
    "Short URL-safe public event reference"
    slots: list[dtm.datetime]
    "All possible slots for the event"
    participants: list[Participant] = Field(default_factory=list)
    "List of participants and their availability"
    created_at: dtm.datetime = Field(default_factory=lambda: dtm.datetime.now(dtm.UTC).replace(microsecond=0))
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
    archive_after: dtm.datetime
    "Time after which the meeting is automatically archived"
    manually_archived_at: dtm.datetime | None = None
    "Time when the owner manually archived the meeting"
    booked_room: BookedRoom | None = None
    "Booked room reference"
    room_booking_in_progress: bool = False
    "Internal guard preventing concurrent room bookings for one meeting"

    class Settings(BeanieDocumentMixin.Settings):
        name = "events"
        indexes: ClassVar[list[Any]] = [
            IndexModel("slug", unique=True),
            "owner_id",
            IndexModel([("owner_id", 1), ("archive_after", -1)]),
            [("created_at", -1)],
            "participants.user_id",
            IndexModel([("participants.user_id", 1), ("archive_after", -1)]),
            "manually_archived_at",
            [
                ("name", "text"),
                ("description", "text"),
            ],
        ]


document_models = [Event]
