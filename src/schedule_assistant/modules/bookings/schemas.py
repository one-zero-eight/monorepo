import datetime as dtm
from enum import StrEnum
from typing import Any, Literal

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
    PENDING_APPROVAL = "pending_approval"
    UNKNOWN = "unknown"
    DECLINED = "declined"
    CANCELLING = "cancelling"


class BookingOutcome(StrEnum):
    SUBMITTED = "submitted"
    PENDING_APPROVAL = "pending_approval"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    UNKNOWN = "unknown"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


class BookingEvidence(ScheduleAssistantSchema):
    operation_id: str | None = None
    outlook_booking_id: str | None = None
    uid: str | None = None
    organizer_mailbox: str | None = None
    room_id: str | None = None
    room_response: Literal["Accept", "Tentative", "Decline", "Unknown", "NoResponseReceived"] | None = "Unknown"
    room_presence: Literal["present", "absent", "unknown"] = "unknown"
    organizer_presence: Literal["present", "absent", "unknown"] = "unknown"
    checked_at: dtm.datetime | None = None
    message_body: str | None = None
    can_cancel: bool = False
    evidence: list[str] = Field(default_factory=list)
    cancellation_status: Literal["cancelling", "cancelled", "requires_review"] | None = None


class BookingItemResultStatus(StrEnum):
    OK = "ok"
    ERROR = "error"


class BookingTaskKind(StrEnum):
    BOOK = "book"
    CANCEL = "cancel"


class BookingTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class BookingTaskItemStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    OK = "ok"
    ERROR = "error"


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
    room_response: str = "Unknown"
    room_presence: Literal["present", "absent", "unknown"] = "unknown"
    checked_at: dtm.datetime | None = None
    message_body: str | None = None
    booking_ids: list[str] = Field(default_factory=list)
    recurrence_start: str | None = None
    recurrence_end: str | None = None
    occurrence_dates: list[str] = Field(default_factory=list)
    covered_dates: list[str] = Field(default_factory=list)
    missing_dates: list[str] = Field(default_factory=list)
    can_cancel: bool = False


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


class ExtraAutoBooking(BookingEvidence):
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


class BatchBookItemResult(BookingEvidence):
    index: str
    "Index in the submitted batch"
    outcome: BookingOutcome = BookingOutcome.UNKNOWN
    status: BookingItemResultStatus
    title: str | None = None
    "Booking title that was submitted"
    error: str | None = None
    "Error message when status is error"


class BatchBookResponse(ScheduleAssistantSchema):
    submitted: int
    "Number of payloads sent to BMP"
    results: list[BatchBookItemResult]


class CancelExtraRequest(ScheduleAssistantSchema):
    scope: Literal["series", "occurrence"]
    occurrence_date: dtm.date | None = None
    extra_ids: list[str]
    "Extra auto-booking ids from the review tree"


class CancelExtraResponse(ScheduleAssistantSchema):
    cancelled: list[str]
    "Successfully cancelled extra ids or outlook ids"
    failed: dict[str, str]
    "Map of extra id → error"
    cancel_requested: list[str] = Field(default_factory=list)
    "Cancellation requests awaiting verified removal"


class CancelBookingRequest(ScheduleAssistantSchema):
    operation_ids: list[str] = Field(default_factory=list)
    booking_ids: list[str] = Field(default_factory=list)
    scope: Literal["series", "occurrence"]
    occurrence_date: dtm.date | None = None


class BookingTaskItem(BookingEvidence):
    index: str
    "Index in the submitted batch, or extra_id for cancel"
    title: str | None = None
    "Human-readable slot or extra label"
    status: BookingTaskItemStatus
    "Transport progress only; room outcome is independent"
    outcome: BookingOutcome = BookingOutcome.UNKNOWN
    slot_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    cancellation_scope: Literal["series", "occurrence"] | None = None
    occurrence_date: dtm.date | None = None
    source_operation_id: str | None = None
    error: str | None = None
    "Error message when status is error"


class BookingTask(ScheduleAssistantSchema):
    task_id: str
    kind: BookingTaskKind
    status: BookingTaskStatus
    sent: int = 0
    "Invites sent; room outcome is tracked separately"
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
