import datetime as dtm
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from src.schedule_assistant.modules.bookings.client import BookingDTO
from src.schedule_assistant.modules.bookings.match import (
    MSK,
    auto_recurrence_fields,
    detect_payload_conflicts,
    extra_booking_candidate_key,
    find_extra_auto_bookings,
    find_matching_auto_booking,
    parse_booking_datetime,
    strip_auto_booking_title_prefix,
)
from src.schedule_assistant.modules.bookings.schemas import (
    BookingReview,
    ConflictHit,
    ConflictMode,
    ExtraAutoBooking,
    ReviewComponent,
    ReviewCourse,
    ReviewKind,
    ReviewProgram,
    ReviewSlot,
)
from src.schedule_assistant.modules.issues.booking_match import booking_as_dict, slot_has_matching_booking
from src.schedule_assistant.modules.issues.booking_slots import BookableSlot

_API_WEEKDAY_TO_PYTHON = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


@dataclass
class ReviewedSlot:
    slot: BookableSlot
    review_kind: ReviewKind | None
    partially_booked: bool
    conflicts: list[tuple[dtm.datetime, dtm.datetime, list[dict[str, Any]]]] = field(default_factory=list)


@dataclass
class ReviewIndex:
    slots: dict[str, ReviewedSlot]
    extras: dict[str, dict[str, Any]]
    tree: BookingReview


def _format_clock(clock: str) -> str:
    if len(clock) >= 5:
        return clock[:5]
    return clock


def _slot_date_label(payload: dict[str, Any]) -> str:
    recurrence = payload.get("recurrence")
    if isinstance(recurrence, dict):
        return str(recurrence.get("weekday") or "").strip().upper() or "WEEKLY"
    start = parse_booking_datetime(str(payload["start"]))
    return start.date().isoformat()


def _slot_times(payload: dict[str, Any]) -> tuple[str, str]:
    start = parse_booking_datetime(str(payload["start"]))
    end = parse_booking_datetime(str(payload["end"]))
    return start.strftime("%H:%M:%S"), end.strftime("%H:%M:%S")


def slot_label(payload: dict[str, Any], *, room: str | None, disabled_reason: str | None) -> str:
    start_time, end_time = _slot_times(payload)
    room_text = room if room else "—"
    suffix = f" ({disabled_reason})" if disabled_reason else ""
    schedule = f"{_slot_date_label(payload)}  {start_time}–{end_time}"
    if isinstance(payload.get("recurrence"), dict):
        schedule = f"Weekly {schedule}"
    return f"{schedule}  @ {room_text}{suffix}"


def _component_label(component_tag: str, audiences: tuple[str, ...]) -> str:
    audience_text = ", ".join(audiences)
    return f"{component_tag} · {audience_text}" if audience_text else component_tag


def _slot_has_own_booking(
    payload: dict[str, Any],
    *,
    auto_bookings: list[dict[str, Any]],
    existing_bookings: list[dict[str, Any]],
) -> bool:
    if find_matching_auto_booking(payload, auto_bookings):
        return True
    return slot_has_matching_booking(
        payload,
        auto_bookings=auto_bookings,
        existing_bookings=existing_bookings,
    )


def classify_slot(
    slot: BookableSlot,
    *,
    auto_bookings: list[dict[str, Any]],
    existing_bookings: list[dict[str, Any]],
) -> ReviewedSlot:
    if not slot.bookable:
        return ReviewedSlot(slot=slot, review_kind=None, partially_booked=False)
    payload = slot.payload
    partially_booked = _slot_has_own_booking(
        payload,
        auto_bookings=auto_bookings,
        existing_bookings=existing_bookings,
    )
    conflicts = detect_payload_conflicts(payload, existing_bookings, auto_bookings=auto_bookings)
    if conflicts:
        return ReviewedSlot(
            slot=slot,
            review_kind=ReviewKind.CONFLICT,
            partially_booked=partially_booked,
            conflicts=conflicts,
        )
    if partially_booked:
        return ReviewedSlot(slot=slot, review_kind=ReviewKind.BOOKED, partially_booked=True)
    return ReviewedSlot(slot=slot, review_kind=ReviewKind.READY, partially_booked=False)


def _can_split(slot: BookableSlot) -> bool:
    return isinstance(slot.payload.get("recurrence"), dict)


def _conflict_hits(reviewed: ReviewedSlot) -> list[ConflictHit]:
    hits: list[ConflictHit] = []
    for start, end, bookings in reviewed.conflicts:
        for booking in bookings:
            hits.append(
                ConflictHit(
                    start=start,
                    end=end,
                    title=str(booking.get("title") or "booking"),
                    room_id=str(booking.get("room_id") or reviewed.slot.payload.get("room_id") or ""),
                )
            )
    return hits


def _to_review_slot(reviewed: ReviewedSlot) -> ReviewSlot:
    slot = reviewed.slot
    payload = slot.payload
    start_time, end_time = _slot_times(payload)
    return ReviewSlot(
        slot_id=slot.slot_id,
        label=slot_label(payload, room=payload.get("room_id"), disabled_reason=slot.disabled_reason),
        date=_slot_date_label(payload),
        start_time=start_time,
        end_time=end_time,
        room=payload.get("room_id"),
        bookable=slot.bookable,
        disabled_reason=slot.disabled_reason,
        recurring=isinstance(payload.get("recurrence"), dict),
        review_kind=reviewed.review_kind,
        partially_booked=reviewed.partially_booked,
        can_split=_can_split(slot) and reviewed.review_kind == ReviewKind.CONFLICT,
        conflicts=_conflict_hits(reviewed),
    )


def _extra_label(booking: dict[str, Any]) -> str:
    title = strip_auto_booking_title_prefix(str(booking.get("title") or "booking"))
    room = str(booking.get("room_id") or "—")
    start = parse_booking_datetime(str(booking["start"]))
    end = parse_booking_datetime(str(booking["end"]))
    recurrence = auto_recurrence_fields(booking.get("recurrence"))
    clock = f"{_format_clock(start.strftime('%H:%M:%S'))}–{_format_clock(end.strftime('%H:%M:%S'))}"
    if recurrence:
        weekday = recurrence["weekday"].capitalize()
        return f"{title}  Weekly {weekday}  {clock}  @ {room}"
    return f"{title}  {start.date().isoformat()}  {clock}  @ {room}"


def _extra_id(booking: dict[str, Any], index: int) -> str:
    return extra_booking_candidate_key(booking) or f"extra|{index}"


def build_review_index(
    slots: list[BookableSlot],
    *,
    auto_bookings: list[BookingDTO],
    existing_bookings: list[BookingDTO],
) -> ReviewIndex:
    auto_dicts = [booking_as_dict(booking) for booking in auto_bookings]
    existing_dicts = [booking_as_dict(booking) for booking in existing_bookings]
    slot_payloads = [slot.payload for slot in slots]

    reviewed_by_id: dict[str, ReviewedSlot] = {}
    grouped: dict[str, dict[str, dict[str, list[ReviewedSlot]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for slot in slots:
        reviewed = classify_slot(slot, auto_bookings=auto_dicts, existing_bookings=existing_dicts)
        reviewed_by_id[slot.slot_id] = reviewed
        grouped[slot.program_name or "Unknown program"][slot.meeting.course_name][slot.component_id].append(reviewed)

    programs: list[ReviewProgram] = []
    for program_name in sorted(grouped, key=str.casefold):
        courses: list[ReviewCourse] = []
        for course_name in sorted(grouped[program_name], key=str.casefold):
            components: list[ReviewComponent] = []
            for component_id, component_slots in grouped[program_name][course_name].items():
                first = component_slots[0].slot
                components.append(
                    ReviewComponent(
                        component_id=component_id,
                        label=_component_label(first.meeting.component_tag, first.audiences),
                        slots=[_to_review_slot(item) for item in component_slots],
                    )
                )
            courses.append(ReviewCourse(course_id=course_name, name=course_name, components=components))
        programs.append(ReviewProgram(program_id=program_name, name=program_name, courses=courses))

    extras: dict[str, dict[str, Any]] = {}
    extra_models: list[ExtraAutoBooking] = []
    for index, booking in enumerate(
        find_extra_auto_bookings(auto_dicts, slot_payloads, existing_bookings=existing_dicts)
    ):
        extra_id = _extra_id(booking, index)
        extras[extra_id] = booking
        extra_models.append(
            ExtraAutoBooking(
                extra_id=extra_id,
                label=_extra_label(booking),
                room_id=str(booking.get("room_id") or ""),
                start=parse_booking_datetime(str(booking["start"])),
                end=parse_booking_datetime(str(booking["end"])),
                title=str(booking.get("title") or ""),
                outlook_booking_id=booking.get("outlook_booking_id"),
                outlook_entry_id=booking.get("outlook_entry_id"),
            )
        )

    return ReviewIndex(
        slots=reviewed_by_id,
        extras=extras,
        tree=BookingReview(programs=programs, extra_auto_bookings=extra_models),
    )


def _first_weekday_on_or_after(weekday_api: str, on_or_after: dtm.date, until: dtm.date) -> dtm.date | None:
    target = _API_WEEKDAY_TO_PYTHON[weekday_api.strip().lower()]
    current = on_or_after
    while current <= until:
        if current.weekday() == target:
            return current
        current += dtm.timedelta(days=1)
    return None


def _calendar_segments_around_conflicts(
    payload: dict[str, Any],
    conflict_dates: set[dtm.date],
) -> list[tuple[dtm.date, dtm.date]]:
    recurrence = payload.get("recurrence")
    if not isinstance(recurrence, dict):
        return []
    term_start = dtm.date.fromisoformat(str(recurrence["start_date"]))
    term_end = dtm.date.fromisoformat(str(recurrence["until_date"]))
    segments: list[tuple[dtm.date, dtm.date]] = []
    cursor = term_start
    for conflict in sorted(conflict_dates):
        until = conflict - dtm.timedelta(days=1)
        if cursor <= until:
            segments.append((cursor, until))
        cursor = conflict + dtm.timedelta(days=1)
    if cursor <= term_end:
        segments.append((cursor, term_end))
    return segments


def split_payloads_around_conflicts(
    slot: BookableSlot,
    conflicts: list[tuple[dtm.datetime, dtm.datetime, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    payload = slot.payload
    recurrence_base = dict(payload.get("recurrence") or {})
    if not recurrence_base:
        return []
    conflict_dates = {start.date() for start, _, _ in conflicts}
    weekday_api = str(recurrence_base["weekday"])
    start_time = parse_booking_datetime(str(payload["start"])).strftime("%H:%M:%S")
    end_time = parse_booking_datetime(str(payload["end"])).strftime("%H:%M:%S")
    payloads: list[dict[str, Any]] = []
    for segment_start, segment_end in _calendar_segments_around_conflicts(payload, conflict_dates):
        first_meeting = _first_weekday_on_or_after(weekday_api, segment_start, segment_end)
        if first_meeting is None:
            continue
        start = dtm.datetime.fromisoformat(f"{first_meeting.isoformat()}T{start_time}").replace(tzinfo=MSK)
        end = dtm.datetime.fromisoformat(f"{first_meeting.isoformat()}T{end_time}").replace(tzinfo=MSK)
        recurrence = dict(recurrence_base)
        recurrence["start_date"] = segment_start.isoformat()
        recurrence["until_date"] = segment_end.isoformat()
        split_payload = dict(payload)
        split_payload["start"] = start.isoformat()
        split_payload["end"] = end.isoformat()
        split_payload["recurrence"] = recurrence
        payloads.append(split_payload)
    return payloads


def collect_booking_payloads(
    index: ReviewIndex,
    slot_ids: list[str],
    conflict_modes: Mapping[str, ConflictMode | str],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for slot_id in slot_ids:
        reviewed = index.slots.get(slot_id)
        if reviewed is None or not reviewed.slot.bookable:
            continue
        if reviewed.review_kind == ReviewKind.BOOKED:
            continue
        mode = str(conflict_modes.get(slot_id, ConflictMode.SKIP))
        if reviewed.review_kind == ReviewKind.CONFLICT:
            if mode == ConflictMode.SKIP:
                continue
            if mode == ConflictMode.SPLIT:
                if not _can_split(reviewed.slot):
                    continue
                payloads.extend(split_payloads_around_conflicts(reviewed.slot, reviewed.conflicts))
                continue
        payloads.append(dict(reviewed.slot.payload))
    return payloads
