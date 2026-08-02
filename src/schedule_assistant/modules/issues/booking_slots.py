import datetime as dtm
from dataclasses import dataclass
from typing import Any, Literal

from src.schedule_assistant.modules.issues.schemas import (
    OccurrencePlacement,
    ScheduledMeeting,
    WeeklyPatternPlacement,
)
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    CoursesConfig,
    SectionsConfig,
    TermConfig,
    WeeklyPatternSlot,
    WeeklyPatternSlotEdit,
)
from src.schedule_assistant.weekday import Weekday, week_start_for_date

VIRTUAL_ROOM_ID = "ONLINE"
_DAY_NAME_TO_BYDAY = {
    Weekday.MONDAY: "MO",
    Weekday.TUESDAY: "TU",
    Weekday.WEDNESDAY: "WE",
    Weekday.THURSDAY: "TH",
    Weekday.FRIDAY: "FR",
    Weekday.SATURDAY: "SA",
    Weekday.SUNDAY: "SU",
}
_BYDAY_TO_API_WEEKDAY = {
    "MO": "monday",
    "TU": "tuesday",
    "WE": "wednesday",
    "TH": "thursday",
    "FR": "friday",
    "SA": "saturday",
    "SU": "sunday",
}
_API_WEEKDAY_TO_PYTHON = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
MSK = dtm.timezone(dtm.timedelta(hours=3))


@dataclass(frozen=True)
class BookableSlot:
    meeting: ScheduledMeeting
    payload: dict[str, Any]
    bookable: bool
    disabled_reason: str | None = None


def _normalize_room(room: str | None) -> str | None:
    if room is None:
        return None
    trimmed = room.strip()
    if not trimmed:
        return None
    if trimmed == VIRTUAL_ROOM_ID:
        return VIRTUAL_ROOM_ID
    return trimmed


def _slot_bookable(room: str | None, known_room_ids: set[str]) -> tuple[bool, str | None]:
    if room is None:
        return False, "no room"
    if room == VIRTUAL_ROOM_ID:
        return False, "online"
    if room not in known_room_ids:
        return False, "unknown room"
    return True, None


def _source_kind(course_tags: list[str]) -> Literal["core_course", "elective"]:
    if "core_course" in course_tags:
        return "core_course"
    return "elective"


def _section_label(course_tags: list[str]) -> str:
    for tag in course_tags:
        if tag == "core_course":
            return "core"
        if tag:
            return tag
    return "unknown"


def _program_code_from_audiences(audiences: list[str]) -> str:
    for audience in audiences:
        code = audience.strip()
        if code.startswith("@"):
            return code.removeprefix("@")
    return audiences[0].strip() if audiences else "unknown"


def build_section_program_maps(
    sections: SectionsConfig,
) -> tuple[dict[str, str], dict[str, str]]:
    group_to_program: dict[str, str] = {}
    selector_to_program: dict[str, str] = {}
    for section in sections.sections:
        for program in section.programs:
            label = f"{section.name} / {program.name}"
            selector_to_program[f"@{program.code}"] = label
            for group in program.groups:
                group_to_program[group] = label
            for track in program.tracks:
                for group in track.groups:
                    group_to_program[group] = label
                selector_to_program[f"@{program.code}/{track.name}"] = label
                selector_to_program[f"@{program.code}/{track.code}"] = label
    return group_to_program, selector_to_program


def _weekday_api_value(day: str | Weekday) -> str:
    if isinstance(day, Weekday):
        return _BYDAY_TO_API_WEEKDAY[_DAY_NAME_TO_BYDAY[day]]
    token = str(day).strip().upper()
    try:
        weekday = Weekday(token)
    except ValueError:
        weekday = None
    if weekday is not None:
        return _BYDAY_TO_API_WEEKDAY[_DAY_NAME_TO_BYDAY[weekday]]
    if len(token) >= 2 and token[:2] in _BYDAY_TO_API_WEEKDAY:
        return _BYDAY_TO_API_WEEKDAY[token[:2]]
    return str(day).strip().lower()


def _weekly_meeting_dates_in_term(term: TermConfig, weekday: str | Weekday) -> list[dtm.date]:
    weekday_api = _weekday_api_value(weekday)
    target = _API_WEEKDAY_TO_PYTHON[weekday_api]
    dates: list[dtm.date] = []
    current = term.semester.start_date
    end = term.semester.end_date
    while current <= end:
        if current.weekday() == target:
            dates.append(current)
        current += dtm.timedelta(days=1)
    return dates


def _edit_for_meeting_date(
    meeting_date: dtm.date,
    edits: list[WeeklyPatternSlotEdit],
    term: TermConfig,
) -> WeeklyPatternSlotEdit | None:
    week_key = week_start_for_date(meeting_date, term.starting_day)
    for edit in edits:
        if week_start_for_date(edit.select_week, term.starting_day) == week_key:
            return edit
    return None


def _edit_changes_meeting(edit: WeeklyPatternSlotEdit) -> bool:
    if edit.cancel:
        return True
    return any(value is not None for value in (edit.date, edit.start_time, edit.end_time, edit.room, edit.instructor))


def _weekly_recurrence_for_segment(
    term: TermConfig, day: str | Weekday, segment_start: dtm.date, segment_end: dtm.date
) -> dict[str, str]:
    return {
        "kind": "weekly_until",
        "weekday": _weekday_api_value(day),
        "start_date": segment_start.isoformat(),
        "until_date": segment_end.isoformat(),
    }


def _recurrence_segments_excluding_edit_weeks(
    term: TermConfig,
    weekday: str | Weekday,
    excluded_week_starts: set[dtm.date],
) -> list[tuple[dtm.date, dtm.date]]:
    meeting_dates = _weekly_meeting_dates_in_term(term, weekday)
    active_dates = [
        meeting_date
        for meeting_date in meeting_dates
        if week_start_for_date(meeting_date, term.starting_day) not in excluded_week_starts
    ]
    if not active_dates:
        return []

    segments: list[tuple[dtm.date, dtm.date]] = []
    group_start = active_dates[0]
    previous = active_dates[0]
    for current in active_dates[1:]:
        if (current - previous).days == 7:
            previous = current
            continue
        segments.append((group_start, previous))
        group_start = current
        previous = current
    segments.append((group_start, previous))
    return segments


def _booking_categories(
    course: CourseConfig,
    audiences: list[str],
) -> list[str]:
    return [
        _section_label(list(course.course_tags)),
        _program_code_from_audiences(audiences),
        course.name,
    ]


def _booking_title(course: CourseConfig, component_tag: str, audiences: list[str]) -> str:
    if component_tag == "lab":
        audience_text = ", ".join(audiences)
        return f"{course.name} ({component_tag}, {audience_text})"
    return f"{course.name} ({component_tag})"


def _slot_datetimes(
    *,
    meeting_date: dtm.date | str,
    start_time: str,
    end_time: str,
    recurrence: dict[str, str] | None,
) -> tuple[dtm.datetime, dtm.datetime]:
    if recurrence:
        range_start = dtm.date.fromisoformat(str(recurrence["start_date"]))
        range_end = dtm.date.fromisoformat(str(recurrence["until_date"]))
        weekday_api = str(recurrence["weekday"]).strip().lower()
        target = _API_WEEKDAY_TO_PYTHON[weekday_api]
        current = range_start
        first_date = range_start
        while current <= range_end:
            if current.weekday() == target:
                first_date = current
                break
            current += dtm.timedelta(days=1)
        meeting_date = first_date
    else:
        meeting_date = dtm.date.fromisoformat(str(meeting_date))

    start = dtm.datetime.fromisoformat(f"{meeting_date.isoformat()}T{start_time}").replace(tzinfo=MSK)
    end = dtm.datetime.fromisoformat(f"{meeting_date.isoformat()}T{end_time}").replace(tzinfo=MSK)
    return start, end


def _build_payload(
    *,
    course: CourseConfig,
    component_tag: str,
    audiences: list[str],
    group_codes: tuple[str, ...],
    source_kind: Literal["core_course", "elective"],
    instructor: str | list[str] | None,
    room: str | None,
    meeting_date: dtm.date | str,
    start_time: str,
    end_time: str,
    placement: OccurrencePlacement | WeeklyPatternPlacement,
    recurrence: dict[str, str] | None = None,
) -> tuple[ScheduledMeeting, dict[str, Any]]:
    start, end = _slot_datetimes(
        meeting_date=meeting_date,
        start_time=start_time,
        end_time=end_time,
        recurrence=recurrence,
    )
    meeting = ScheduledMeeting(
        course_name=course.name,
        component_tag=component_tag,
        source_kind=source_kind,
        placement=placement,
        start_time=dtm.time.fromisoformat(start_time[:8]),
        end_time=dtm.time.fromisoformat(end_time[:8]),
        room=room,
        instructor=instructor,
        groups=group_codes,
    )
    payload: dict[str, Any] = {
        "room_id": room,
        "title": _booking_title(course, component_tag, audiences),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "participant_emails": [],
        "categories": _booking_categories(course, audiences),
    }
    if recurrence is not None:
        payload["recurrence"] = recurrence
    return meeting, payload


def _slots_from_weekly_pattern(
    *,
    course: CourseConfig,
    component_tag: str,
    audiences: list[str],
    group_codes: tuple[str, ...],
    pattern: WeeklyPatternSlot,
    term: TermConfig,
    known_room_ids: set[str],
    instructor: str | list[str] | None,
) -> list[BookableSlot]:
    edits = list(pattern.edits or [])
    day_label = pattern.weekday
    start_time = pattern.start_time.strftime("%H:%M:%S")
    end_time = pattern.end_time.strftime("%H:%M:%S")
    base_room = _normalize_room(pattern.room)
    source_kind = _source_kind(course.course_tags)
    slots: list[BookableSlot] = []
    excluded_week_starts: set[dtm.date] = set()

    for meeting_date in _weekly_meeting_dates_in_term(term, day_label):
        edit = _edit_for_meeting_date(meeting_date, edits, term)
        if edit is None or not _edit_changes_meeting(edit):
            continue
        excluded_week_starts.add(week_start_for_date(meeting_date, term.starting_day))
        if edit.cancel:
            continue
        resolved_date = edit.date if edit.date else meeting_date
        resolved_start = (edit.start_time if edit.start_time else pattern.start_time).strftime("%H:%M:%S")
        resolved_end = (edit.end_time if edit.end_time else pattern.end_time).strftime("%H:%M:%S")
        resolved_room = _normalize_room(edit.room if edit.room else pattern.room)
        resolved_instructor = edit.instructor if edit.instructor is not None else instructor
        bookable, reason = _slot_bookable(resolved_room, known_room_ids)
        meeting, payload = _build_payload(
            course=course,
            component_tag=component_tag,
            audiences=audiences,
            group_codes=group_codes,
            source_kind=source_kind,
            instructor=resolved_instructor,
            room=resolved_room,
            meeting_date=resolved_date,
            start_time=resolved_start,
            end_time=resolved_end,
            placement=OccurrencePlacement(date=resolved_date),
        )
        slots.append(BookableSlot(meeting=meeting, payload=payload, bookable=bookable, disabled_reason=reason))

    for segment_start, segment_end in _recurrence_segments_excluding_edit_weeks(term, day_label, excluded_week_starts):
        recurrence = _weekly_recurrence_for_segment(term, day_label, segment_start, segment_end)
        bookable, reason = _slot_bookable(base_room, known_room_ids)
        meeting, payload = _build_payload(
            course=course,
            component_tag=component_tag,
            audiences=audiences,
            group_codes=group_codes,
            source_kind=source_kind,
            instructor=instructor,
            room=base_room,
            meeting_date=str(day_label),
            start_time=start_time,
            end_time=end_time,
            placement=WeeklyPatternPlacement(weekday=pattern.weekday, edits=edits),
            recurrence=recurrence,
        )
        slots.append(BookableSlot(meeting=meeting, payload=payload, bookable=bookable, disabled_reason=reason))

    return slots


def _session_audiences(component: CourseConfig.Component, session: ComponentSessionSeries) -> list[str]:
    if session.audience:
        return list(session.audience)
    return list(component.student_groups)


def build_bookable_slots(
    courses: CoursesConfig,
    sections: SectionsConfig,
    term: TermConfig,
    known_room_ids: set[str],
) -> list[BookableSlot]:
    from src.schedule_assistant.modules.schedule_config.validation import build_selector_map, expand_group_tokens

    selector_map = build_selector_map(sections)
    slots: list[BookableSlot] = []

    for course in courses.courses:
        source_kind = _source_kind(course.course_tags)
        for component in course.components:
            if not component.sessions:
                continue
            for session in component.sessions:
                audiences = _session_audiences(component, session)
                if not audiences:
                    continue
                group_codes = tuple(sorted(expand_group_tokens(audiences, selector_map)))
                instructor = None
                if session.occurrences:
                    instructor = session.occurrences[0].instructor
                elif session.weekly_pattern:
                    instructor = session.weekly_pattern[0].instructor

                for occurrence in session.occurrences or []:
                    start_time = occurrence.start_time.strftime("%H:%M:%S")
                    end_time = occurrence.end_time.strftime("%H:%M:%S")
                    room = _normalize_room(occurrence.room)
                    bookable, reason = _slot_bookable(room, known_room_ids)
                    meeting, payload = _build_payload(
                        course=course,
                        component_tag=str(component.tag),
                        audiences=audiences,
                        group_codes=group_codes,
                        source_kind=source_kind,
                        instructor=occurrence.instructor,
                        room=room,
                        meeting_date=occurrence.date,
                        start_time=start_time,
                        end_time=end_time,
                        placement=OccurrencePlacement(date=occurrence.date),
                    )
                    slots.append(
                        BookableSlot(meeting=meeting, payload=payload, bookable=bookable, disabled_reason=reason)
                    )

                for pattern in session.weekly_pattern or []:
                    pattern_instructor = pattern.instructor if pattern.instructor is not None else instructor
                    slots.extend(
                        _slots_from_weekly_pattern(
                            course=course,
                            component_tag=str(component.tag),
                            audiences=audiences,
                            group_codes=group_codes,
                            pattern=pattern,
                            term=term,
                            known_room_ids=known_room_ids,
                            instructor=pattern_instructor,
                        ),
                    )

    return slots
