import datetime as dtm
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from src.schedule_assistant.modules.bookings.client import BookingDTO
from src.schedule_assistant.modules.bookings.match import (
    BookingCoverage,
    auto_recurrence_fields,
    booking_coverage,
    detect_payload_conflicts,
    extra_booking_candidate_key,
    find_extra_auto_bookings,
    iter_payload_occurrences,
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
from src.schedule_assistant.modules.issues.booking_match import booking_as_dict
from src.schedule_assistant.modules.issues.booking_slots import BookableSlot

_WEEKDAY_NAME_RU = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)

_EVERY_WEEKDAY_RU = {
    "monday": "Каждый понедельник",
    "tuesday": "Каждый вторник",
    "wednesday": "Каждую среду",
    "thursday": "Каждый четверг",
    "friday": "Каждую пятницу",
    "saturday": "Каждую субботу",
    "sunday": "Каждое воскресенье",
}


@dataclass
class ReviewedSlot:
    slot: BookableSlot
    review_kind: ReviewKind | None
    partially_booked: bool
    conflicts: list[tuple[dtm.datetime, dtm.datetime, list[dict[str, Any]]]] = field(default_factory=list)
    coverage: BookingCoverage = field(default_factory=BookingCoverage)


@dataclass
class ReviewIndex:
    slots: dict[str, ReviewedSlot]
    extras: dict[str, dict[str, Any]]
    tree: BookingReview


def _format_clock(clock: str) -> str:
    if len(clock) >= 5:
        return clock[:5]
    return clock


def _room_suffix(room: str | None) -> str:
    if not room:
        return ""
    return f" ({room})"


def _weekly_when(weekday: str, start_time: str, end_time: str, room: str | None) -> str:
    key = weekday.strip().lower()
    phrase = _EVERY_WEEKDAY_RU.get(key, f"Каждый {weekday.strip().lower() or 'день'}")
    return f"{phrase} {_format_clock(start_time)}–{_format_clock(end_time)}{_room_suffix(room)}"


def _occurrence_when(start: dtm.datetime, end: dtm.datetime, room: str | None) -> str:
    date = f"{start.day:02d}.{start.month:02d}.{start.year}"
    weekday = _WEEKDAY_NAME_RU[start.weekday()]
    return (
        f"{weekday} {date} {_format_clock(start.strftime('%H:%M:%S'))}–{_format_clock(end.strftime('%H:%M:%S'))}"
        f"{_room_suffix(room)}"
    )


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
    recurrence = payload.get("recurrence")
    if isinstance(recurrence, dict):
        start_time, end_time = _slot_times(payload)
        label = _weekly_when(str(recurrence.get("weekday") or ""), start_time, end_time, room)
        if int(recurrence.get("interval", 1)) == 2:
            label += f" · Every other week (first: {recurrence['start_date']})"
    else:
        start = parse_booking_datetime(str(payload["start"]))
        end = parse_booking_datetime(str(payload["end"]))
        label = _occurrence_when(start, end, room)
    if disabled_reason:
        return f"{label} ({disabled_reason})"
    return label


def _component_label(component_tag: str, audiences: tuple[str, ...]) -> str:
    audience_text = ", ".join(audiences)
    return f"{component_tag} · {audience_text}" if audience_text else component_tag


def classify_slot(
    slot: BookableSlot,
    *,
    auto_bookings: list[dict[str, Any]],
    existing_bookings: list[dict[str, Any]],
) -> ReviewedSlot:
    payload = slot.payload
    coverage = booking_coverage(payload, auto_bookings, existing_bookings)
    if not slot.bookable:
        return ReviewedSlot(slot=slot, review_kind=None, partially_booked=False, coverage=coverage)
    conflicts = detect_payload_conflicts(payload, existing_bookings, auto_bookings=auto_bookings)
    responses = {str(booking.get("room_response") or "unknown").casefold() for booking in coverage.bookings}
    if any(booking.get("cancellation_status") == "cancelling" for booking in coverage.bookings):
        kind = ReviewKind.CANCELLING
    elif conflicts:
        kind = ReviewKind.CONFLICT
    elif any(booking.get("room_presence") == "absent" for booking in coverage.bookings):
        kind = ReviewKind.DECLINED if responses & {"declined", "decline"} else ReviewKind.UNKNOWN
    elif coverage.uncertain or (coverage.bookings and coverage.missing):
        kind = ReviewKind.UNKNOWN
    elif coverage.bookings:
        if responses <= {"accepted", "accept"}:
            kind = ReviewKind.BOOKED
        elif responses & {"declined", "decline"}:
            kind = ReviewKind.DECLINED
        elif responses <= {"accepted", "accept", "tentative"}:
            kind = ReviewKind.PENDING_APPROVAL
        else:
            kind = ReviewKind.UNKNOWN
    else:
        kind = ReviewKind.READY
    return ReviewedSlot(
        slot=slot,
        review_kind=kind,
        partially_booked=bool(coverage.covered),
        conflicts=conflicts,
        coverage=coverage,
    )


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
    coverage = reviewed.coverage
    bookings = coverage.bookings
    responses = {booking.get("room_response") or "unknown" for booking in bookings}
    presences = {booking.get("room_presence") or "unknown" for booking in bookings}
    checked = [booking["checked_at"] for booking in bookings if booking.get("checked_at")]
    booking_ids = sorted(
        {str(booking["outlook_booking_id"]) for booking in bookings if booking.get("outlook_booking_id")}
    )
    dates = sorted({start.date().isoformat() for start, _ in coverage.expected})
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
        room_response=next(iter(responses)) if len(responses) == 1 else "unknown",
        room_presence="present" if presences == {"present"} else "absent" if presences == {"absent"} else "unknown",
        checked_at=min(checked) if len(checked) == len(bookings) and checked else None,
        message_body="\n\n".join(
            dict.fromkeys(str(booking["message_body"]) for booking in bookings if booking.get("message_body"))
        )
        or None,
        booking_ids=booking_ids,
        recurrence_start=dates[0] if dates and _can_split(slot) else None,
        recurrence_end=dates[-1] if dates and _can_split(slot) else None,
        occurrence_dates=dates,
        covered_dates=sorted({start.date().isoformat() for start, _ in coverage.covered}),
        missing_dates=sorted({start.date().isoformat() for start, _ in coverage.missing}),
        can_cancel=bool(bookings) and all(booking.get("can_cancel", False) for booking in bookings),
    )


def _extra_label(booking: dict[str, Any]) -> str:
    title = strip_auto_booking_title_prefix(str(booking.get("title") or "booking"))
    room = str(booking.get("room_id") or "") or None
    start = parse_booking_datetime(str(booking["start"]))
    end = parse_booking_datetime(str(booking["end"]))
    recurrence = auto_recurrence_fields(booking.get("recurrence"))
    if recurrence:
        when = _weekly_when(
            recurrence["weekday"],
            start.strftime("%H:%M:%S"),
            end.strftime("%H:%M:%S"),
            room,
        )
    else:
        when = _occurrence_when(start, end, room)
    return f"{title} · {when}"


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
        retained = set().union(*(booking_coverage(payload, [booking]).covered for payload in slot_payloads))
        extras[extra_id] = {**booking, "can_cancel": bool(booking.get("can_cancel")) and not retained}
        extra_models.append(
            ExtraAutoBooking(
                extra_id=extra_id,
                label=_extra_label(booking)
                + (" · Требуется проверка лишних повторений; не отменять всю серию" if retained else ""),
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


def split_payloads_around_conflicts(
    slot: BookableSlot,
    conflicts: list[tuple[dtm.datetime, dtm.datetime, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    payload = slot.payload
    recurrence_base = dict(payload.get("recurrence") or {})
    if not recurrence_base:
        return []
    conflict_dates = {start.date() for start, _, _ in conflicts}
    occurrences = [
        (start, end) for start, end in iter_payload_occurrences(payload) if start.date() not in conflict_dates
    ]
    segments: list[list[tuple[dtm.datetime, dtm.datetime]]] = []
    step = dtm.timedelta(weeks=int(recurrence_base.get("interval", 1)))
    for start, end in occurrences:
        if not segments or start - segments[-1][-1][0] != step or end - segments[-1][-1][1] != step:
            segments.append([])
        segments[-1].append((start, end))
    payloads = []
    for segment in segments:
        start, end = segment[0]
        recurrence = {
            **recurrence_base,
            "weekday": start.strftime("%A").lower(),
            "start_date": start.date().isoformat(),
            "until_date": segment[-1][0].date().isoformat(),
        }
        split_payload = {**payload, "start": start.isoformat(), "end": end.isoformat(), "recurrence": recurrence}
        split_payload.pop("deleted_occurrences", None)
        split_payload.pop("modified_occurrences", None)
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
        if (
            reviewed.review_kind
            in {
                ReviewKind.BOOKED,
                ReviewKind.PENDING_APPROVAL,
                ReviewKind.UNKNOWN,
                ReviewKind.DECLINED,
                ReviewKind.CANCELLING,
            }
            or reviewed.partially_booked
        ):
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
