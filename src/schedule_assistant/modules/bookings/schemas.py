import datetime as dtm
from enum import StrEnum
from typing import Literal

from pydantic import Field

from src.schedule_assistant.schema_base import ScheduleAssistantSchema


class ConflictMode(StrEnum):
    SKIP = "skip"
    BOOK = "book"
    SPLIT = "split"


class ReviewKind(StrEnum):
    READY = "ready"
    BOOKED = "booked"
    CONFLICT = "conflict"


class ConflictHit(ScheduleAssistantSchema):
    start: dtm.datetime
    "Occurrence start that overlaps an existing booking"
    end: dtm.datetime
    "Occurrence end that overlaps an existing booking"
    title: str
    "Title of the overlapping Outlook booking"
    room_id: str
    "Room of the overlapping booking"


class ReviewSlot(ScheduleAssistantSchema):
    slot_id: str
    "Stable id for this bookable slot"
    label: str
    "Human-readable schedule line"
    date: str
    "ISO date for a one-off slot, or weekday name for a weekly series"
    start_time: str
    "Slot start time HH:MM:SS"
    end_time: str
    "Slot end time HH:MM:SS"
    room: str | None = None
    "Room id to book, if any"
    bookable: bool
    "False when the room is missing, online, or unknown"
    disabled_reason: str | None = None
    "Why the slot cannot be booked"
    recurring: bool = False
    "True for weekly series payloads"
    review_kind: ReviewKind | None = None
    "Classification against current Outlook bookings"
    partially_booked: bool = False
    "True when this slot already has a matching auto-booking"
    can_split: bool = False
    "True when a weekly conflict can be booked around conflicting dates"
    conflicts: list[ConflictHit] = Field(default_factory=list)
    "Overlapping foreign Outlook bookings"


class ReviewComponent(ScheduleAssistantSchema):
    component_id: str
    "Stable id for the course component + audience session"
    label: str
    "Component tag and audiences"
    slots: list[ReviewSlot]


class ReviewCourse(ScheduleAssistantSchema):
    course_id: str
    "Course name"
    name: str
    "Course display name"
    components: list[ReviewComponent]


class ReviewProgram(ScheduleAssistantSchema):
    program_id: str
    "Program track label"
    name: str
    "Program track label"
    courses: list[ReviewCourse]


class ExtraAutoBooking(ScheduleAssistantSchema):
    extra_id: str
    "Stable id used to cancel this extra booking"
    label: str
    "Human-readable extra booking line"
    room_id: str
    "Booked room"
    start: dtm.datetime
    "Booking start"
    end: dtm.datetime
    "Booking end"
    title: str
    "Outlook title"
    outlook_booking_id: str | None = None
    "BMP calendar item id when we can manage the booking"
    outlook_entry_id: str | None = None
    "Room-calendar entry id fallback"


class BookingReview(ScheduleAssistantSchema):
    programs: list[ReviewProgram]
    extra_auto_bookings: list[ExtraAutoBooking] = Field(default_factory=list)


class BatchBookRequest(ScheduleAssistantSchema):
    slot_ids: list[str]
    "Selected slot ids from the review tree"
    conflict_modes: dict[str, ConflictMode] = Field(default_factory=dict)
    "Per-slot action for conflict rows: skip, book, or split"


class BatchBookItemResult(ScheduleAssistantSchema):
    index: str
    "Index in the submitted batch"
    status: Literal["ok", "error"]
    title: str | None = None
    "Booking title that was submitted"
    error: str | None = None
    "Error message when status is error"


class BatchBookResponse(ScheduleAssistantSchema):
    submitted: int
    "Number of payloads sent to BMP"
    results: list[BatchBookItemResult]


class CancelExtraRequest(ScheduleAssistantSchema):
    extra_ids: list[str]
    "Extra auto-booking ids from the review tree"


class CancelExtraResponse(ScheduleAssistantSchema):
    cancelled: list[str]
    "Successfully cancelled extra ids or outlook ids"
    failed: dict[str, str]
    "Map of extra id → error"


class BookingTaskItem(ScheduleAssistantSchema):
    index: str
    "Index in the submitted batch, or extra_id for cancel"
    title: str | None = None
    "Human-readable slot or extra label"
    status: Literal["pending", "sent", "ok", "error"]
    "pending → sent (invite left) → ok (Accept) / error"
    error: str | None = None
    "Error message when status is error"


class BookingTask(ScheduleAssistantSchema):
    task_id: str
    kind: Literal["book", "cancel"]
    status: Literal["queued", "running", "done", "error"]
    sent: int = 0
    "Invites sent, waiting for room Accept"
    done: int = 0
    "Items that already finished (ok or error)"
    total: int = 0
    current: str | None = None
    "Title of the last updated item"
    items: list[BookingTaskItem] = Field(default_factory=list)
    error: str | None = None
    "Task-level failure"
    book: BatchBookResponse | None = None
    cancel: CancelExtraResponse | None = None
