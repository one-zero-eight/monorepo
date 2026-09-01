import datetime as dtm
from collections import Counter
from dataclasses import dataclass
from typing import Any

from src.schedule_assistant.modules.schedule_config.schemas import (
    CourseConfig,
    TermConfig,
    WeeklyPatternSlot,
    WeeklyPatternSlotEdit,
)
from src.schedule_assistant.modules.schedule_config.semester_windows import (
    meeting_dates_in_window,
    resolve_audience_semester,
)
from src.schedule_assistant.weekday import Weekday, week_start_for_date


@dataclass(frozen=True)
class WeeklyPatternCanonicalizationStats:
    courses_changed: int = 0
    slots_changed: int = 0
    edits_before: int = 0
    edits_after: int = 0

    def __add__(
        self,
        other: WeeklyPatternCanonicalizationStats,
    ) -> WeeklyPatternCanonicalizationStats:
        return WeeklyPatternCanonicalizationStats(
            courses_changed=self.courses_changed + other.courses_changed,
            slots_changed=self.slots_changed + other.slots_changed,
            edits_before=self.edits_before + other.edits_before,
            edits_after=self.edits_after + other.edits_after,
        )


@dataclass(frozen=True)
class _Occurrence:
    source_week: dtm.date
    date: dtm.date | None
    start_time: dtm.time | None
    end_time: dtm.time | None
    room: str | None
    instructor: str | list[str] | None

    @property
    def cancelled(self) -> bool:
        return self.date is None


type _InstructorKey = tuple[str, ...] | None
type _BaseSignature = tuple[Weekday, dtm.time, dtm.time, str | None, _InstructorKey]


def _instructor_key(value: str | list[str] | None) -> tuple[str, ...] | None:
    if isinstance(value, str):
        return ("str", value)
    if value is None:
        return None
    return ("list", *value)


def _signature(
    weekday: Weekday,
    start_time: dtm.time,
    end_time: dtm.time,
    room: str | None,
    instructor: str | list[str] | None,
) -> _BaseSignature:
    return weekday, start_time, end_time, room, _instructor_key(instructor)


def _signature_from_occurrence(occurrence: _Occurrence) -> _BaseSignature | None:
    if occurrence.cancelled:
        return None
    assert occurrence.date is not None
    assert occurrence.start_time is not None
    assert occurrence.end_time is not None
    return _signature(
        Weekday(list(Weekday)[occurrence.date.weekday()]),
        occurrence.start_time,
        occurrence.end_time,
        occurrence.room,
        occurrence.instructor,
    )


def _pattern_dates(slot: WeeklyPatternSlot, term: TermConfig, audiences: list[str]) -> list[dtm.date]:
    window = resolve_audience_semester(term, audiences)
    if window is None or (term.days and slot.weekday not in term.days):
        return []
    return meeting_dates_in_window(window, slot.weekday.index)


def _expand_slot(slot: WeeklyPatternSlot, term: TermConfig, audiences: list[str]) -> list[_Occurrence]:
    edits_by_week = {week_start_for_date(edit.select_week, term.starting_day): edit for edit in (slot.edits or [])}
    occurrences: list[_Occurrence] = []
    for pattern_date in _pattern_dates(slot, term, audiences):
        source_week = week_start_for_date(pattern_date, term.starting_day)
        edit = edits_by_week.get(source_week)
        if edit is not None and edit.cancel:
            occurrences.append(
                _Occurrence(
                    source_week=source_week,
                    date=None,
                    start_time=None,
                    end_time=None,
                    room=None,
                    instructor=None,
                )
            )
            continue
        occurrences.append(
            _Occurrence(
                source_week=source_week,
                date=edit.date if edit is not None and edit.date is not None else pattern_date,
                start_time=(edit.start_time if edit is not None and edit.start_time is not None else slot.start_time),
                end_time=edit.end_time if edit is not None and edit.end_time is not None else slot.end_time,
                room=edit.room if edit is not None and edit.room is not None else slot.room,
                instructor=(edit.instructor if edit is not None and edit.instructor is not None else slot.instructor),
            )
        )
    return occurrences


def _slot_from_signature(signature: _BaseSignature) -> WeeklyPatternSlot:
    weekday, start_time, end_time, room, instructor = signature
    instructor_value: str | list[str] | None
    if instructor is None:
        instructor_value = None
    elif instructor[0] == "str":
        instructor_value = instructor[1]
    else:
        instructor_value = list(instructor[1:])
    return WeeklyPatternSlot(
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
        room=room,
        instructor=instructor_value,
    )


def _rebuild_slot(
    signature: _BaseSignature,
    occurrences: list[_Occurrence],
    term: TermConfig,
    audiences: list[str],
) -> WeeklyPatternSlot | None:
    candidate = _slot_from_signature(signature)
    candidate_dates = _pattern_dates(candidate, term, audiences)
    dates_by_week = {
        week_start_for_date(pattern_date, term.starting_day): pattern_date for pattern_date in candidate_dates
    }
    occurrences_by_week = {occurrence.source_week: occurrence for occurrence in occurrences}
    if not occurrences_by_week.keys() <= dates_by_week.keys():
        return None

    edits: list[WeeklyPatternSlotEdit] = []
    for source_week, pattern_date in dates_by_week.items():
        occurrence = occurrences_by_week.get(source_week)
        if occurrence is None or occurrence.cancelled:
            edits.append(WeeklyPatternSlotEdit(select_week=pattern_date, cancel=True))
            continue

        edit_payload: dict[str, Any] = {"select_week": pattern_date}
        if occurrence.date != pattern_date:
            edit_payload["date"] = occurrence.date
        if occurrence.start_time != candidate.start_time:
            edit_payload["start_time"] = occurrence.start_time
        if occurrence.end_time != candidate.end_time:
            edit_payload["end_time"] = occurrence.end_time
        if occurrence.room != candidate.room:
            edit_payload["room"] = occurrence.room
        if _instructor_key(occurrence.instructor) != _instructor_key(candidate.instructor):
            edit_payload["instructor"] = occurrence.instructor
        if len(edit_payload) > 1:
            edits.append(WeeklyPatternSlotEdit.model_validate(edit_payload))

    return candidate.model_copy(update={"edits": edits or None})


def _semantic_key(occurrences: list[_Occurrence]) -> Counter[tuple[Any, ...]]:
    return Counter(
        (
            occurrence.date,
            occurrence.start_time,
            occurrence.end_time,
            occurrence.room,
            _instructor_key(occurrence.instructor),
        )
        for occurrence in occurrences
        if not occurrence.cancelled
    )


def canonicalize_weekly_slot(
    slot: WeeklyPatternSlot,
    term: TermConfig,
    audiences: list[str],
) -> WeeklyPatternSlot:
    occurrences = _expand_slot(slot, term, audiences)
    if not occurrences:
        return slot

    current_signature = _signature(
        slot.weekday,
        slot.start_time,
        slot.end_time,
        slot.room,
        slot.instructor,
    )
    frequencies = Counter(
        signature for occurrence in occurrences if (signature := _signature_from_occurrence(occurrence)) is not None
    )
    candidate_signatures = set(frequencies)
    candidate_signatures.add(current_signature)

    candidates: list[tuple[int, bool, int, str, WeeklyPatternSlot]] = []
    before_key = _semantic_key(occurrences)
    for signature in candidate_signatures:
        candidate = _rebuild_slot(signature, occurrences, term, audiences)
        if candidate is None:
            continue
        if _semantic_key(_expand_slot(candidate, term, audiences)) != before_key:
            continue
        candidates.append(
            (
                frequencies[signature],
                signature == current_signature,
                -len(candidate.edits or []),
                repr(signature),
                candidate,
            )
        )

    if not candidates:
        return slot
    best = max(candidates, key=lambda candidate: candidate[:4])[4]
    if len(best.edits or []) >= len(slot.edits or []):
        return slot
    return best


def canonicalize_courses(
    courses: list[CourseConfig],
    term: TermConfig | None,
    *,
    course_names: set[str] | None = None,
) -> tuple[list[CourseConfig], WeeklyPatternCanonicalizationStats]:
    if term is None:
        return courses, WeeklyPatternCanonicalizationStats()

    normalized_courses: list[CourseConfig] = []
    total_stats = WeeklyPatternCanonicalizationStats()
    for course in courses:
        if course_names is not None and course.name not in course_names:
            normalized_courses.append(course)
            continue

        course_slots_changed = 0
        edits_before = 0
        edits_after = 0
        components = []
        for component in course.components:
            sessions = []
            for session in component.sessions or []:
                audiences = list(session.audience or component.audience)
                weekly_pattern = []
                for slot in session.weekly_pattern or []:
                    normalized_slot = canonicalize_weekly_slot(slot, term, audiences)
                    if normalized_slot != slot:
                        course_slots_changed += 1
                        edits_before += len(slot.edits or [])
                        edits_after += len(normalized_slot.edits or [])
                    weekly_pattern.append(normalized_slot)
                sessions.append(
                    session.model_copy(
                        update={"weekly_pattern": weekly_pattern or None},
                    )
                )
            components.append(
                component.model_copy(
                    update={"sessions": sessions or None},
                )
            )
        normalized_course = course.model_copy(update={"components": components})
        normalized_courses.append(normalized_course)
        if course_slots_changed:
            total_stats += WeeklyPatternCanonicalizationStats(
                courses_changed=1,
                slots_changed=course_slots_changed,
                edits_before=edits_before,
                edits_after=edits_after,
            )

    return normalized_courses, total_stats
