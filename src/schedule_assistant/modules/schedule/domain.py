import datetime as dtm

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
    SessionOccurrence,
    TermConfig,
    WeeklyPatternSlot,
)
from src.schedule_assistant.modules.schedule_config.semester_windows import resolve_audience_semester
from src.schedule_assistant.modules.schedule_config.validation import build_selector_map, expand_group_tokens
from src.schedule_assistant.modules.schedule_config.weekly_dates import expand_weekly_slot, normalize_alternation
from src.schedule_assistant.weekday import Weekday


def _group_codes_for_session(
    component_groups: list[str],
    session: ComponentSessionSeries,
    selector_map: dict[str, set[str]],
) -> tuple[str, ...]:
    tokens = session.audience or component_groups
    return tuple(sorted(expand_group_tokens(tokens, selector_map)))


def _enrollment_size(group_codes: tuple[str, ...], sections: SectionsConfig) -> int | None:
    groups_by_code = {group.code: group for group in sections.students_groups}
    sizes: list[int] = []
    for code in group_codes:
        group = groups_by_code.get(code)
        if group is None:
            continue
        if group.estimated_size is not None:
            sizes.append(group.estimated_size)
        elif group.students:
            sizes.append(len(group.students))
    return sum(sizes) if sizes else None


def _base_meeting(
    *,
    course: CourseConfig,
    component_tag: str,
    group_codes: tuple[str, ...],
    students_number: int | None,
    placement: OccurrencePlacement | WeeklyPatternPlacement,
    start_time: dtm.time,
    end_time: dtm.time,
    room: str | None,
    instructor: str | list[str] | None,
    notes: str,
) -> ScheduledMeeting:
    return ScheduledMeeting(
        course_name=course.name,
        component_tag=component_tag,
        placement=placement,
        start_time=start_time,
        end_time=end_time,
        room=room,
        instructor=instructor,
        groups=group_codes,
        students_number=students_number,
        notes=notes,
    )


def _meeting_from_occurrence(
    course: CourseConfig,
    component_tag: str,
    group_codes: tuple[str, ...],
    students_number: int | None,
    occurrence: SessionOccurrence,
    series_notes: str,
) -> ScheduledMeeting:
    return _base_meeting(
        course=course,
        component_tag=component_tag,
        group_codes=group_codes,
        students_number=students_number,
        placement=OccurrencePlacement(date=occurrence.date),
        start_time=occurrence.start_time,
        end_time=occurrence.end_time,
        room=occurrence.room,
        instructor=occurrence.instructor,
        notes=occurrence.notes if occurrence.notes is not None else series_notes,
    )


def _meeting_from_weekly_slot(
    course: CourseConfig,
    component_tag: str,
    group_codes: tuple[str, ...],
    students_number: int | None,
    slot: WeeklyPatternSlot,
    series_notes: str,
    *,
    term: TermConfig | None = None,
    audiences: list[str] | None = None,
) -> ScheduledMeeting:
    window = resolve_audience_semester(term, audiences or []) if term is not None else None
    return _base_meeting(
        course=course,
        component_tag=component_tag,
        group_codes=group_codes,
        students_number=students_number,
        placement=WeeklyPatternPlacement(
            weekday=slot.weekday,
            alternation=normalize_alternation(slot.alternation, term.starting_day if term else Weekday.MONDAY),
            edits=slot.edits or [],
            start_date=window.start_date if window is not None else None,
            end_date=window.end_date if window is not None else None,
            starting_day=term.starting_day if term is not None else Weekday.MONDAY,
        ),
        start_time=slot.start_time,
        end_time=slot.end_time,
        room=slot.room,
        instructor=slot.instructor,
        notes=series_notes,
    )


def _meetings_from_weekly_slot_concrete(
    course: CourseConfig,
    component_tag: str,
    group_codes: tuple[str, ...],
    students_number: int | None,
    slot: WeeklyPatternSlot,
    series_notes: str,
    *,
    term: TermConfig,
    audiences: list[str],
) -> list[ScheduledMeeting]:
    window = resolve_audience_semester(term, audiences)
    if window is None or (term.days and slot.weekday not in term.days):
        return []

    return [
        _meeting_from_occurrence(course, component_tag, group_codes, students_number, resolved.occurrence, series_notes)
        for resolved in expand_weekly_slot(slot, window, term.starting_day)
        if resolved.occurrence is not None
    ]


def meetings_from_schedule_config(
    courses: CoursesConfig,
    sections: SectionsConfig,
    term: TermConfig | None = None,
    *,
    expand_weekly: bool | None = None,
) -> list[ScheduledMeeting]:
    """Build scheduled meetings, optionally expanding weekly patterns to concrete dates."""
    selector_map = build_selector_map(sections)
    should_expand = expand_weekly if expand_weekly is not None else term is not None
    meetings: list[ScheduledMeeting] = []

    for course in courses.courses:
        for component in course.components:
            if not component.sessions:
                continue
            for session in component.sessions:
                group_codes = _group_codes_for_session(component.audience, session, selector_map)
                students_number = component.expected_enrollment
                if students_number is None:
                    students_number = _enrollment_size(group_codes, sections)
                audiences = list(session.audience or component.audience)

                for occurrence in session.dates_pattern or []:
                    meetings.append(
                        _meeting_from_occurrence(
                            course,
                            component.tag,
                            group_codes,
                            students_number,
                            occurrence,
                            session.notes,
                        )
                    )
                for slot in session.weekly_pattern or []:
                    if term is not None and (
                        resolve_audience_semester(term, audiences) is None
                        or (term.days and slot.weekday not in term.days)
                    ):
                        continue
                    if should_expand and term is not None:
                        meetings.extend(
                            _meetings_from_weekly_slot_concrete(
                                course,
                                component.tag,
                                group_codes,
                                students_number,
                                slot,
                                session.notes,
                                term=term,
                                audiences=audiences,
                            )
                        )
                    else:
                        meetings.append(
                            _meeting_from_weekly_slot(
                                course,
                                component.tag,
                                group_codes,
                                students_number,
                                slot,
                                session.notes,
                                term=term,
                                audiences=audiences,
                            )
                        )
    return meetings
