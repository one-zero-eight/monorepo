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
from src.schedule_assistant.modules.schedule_config.semester_windows import (
    meeting_dates_in_window,
    resolve_audience_semester,
)
from src.schedule_assistant.modules.schedule_config.validation import build_selector_map, expand_group_tokens
from src.schedule_assistant.weekday import week_start_for_date, weekday_index


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
    )


def _meeting_from_occurrence(
    course: CourseConfig,
    component_tag: str,
    group_codes: tuple[str, ...],
    students_number: int | None,
    occurrence: SessionOccurrence,
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
    )


def _meeting_from_weekly_slot(
    course: CourseConfig,
    component_tag: str,
    group_codes: tuple[str, ...],
    students_number: int | None,
    slot: WeeklyPatternSlot,
) -> ScheduledMeeting:
    return _base_meeting(
        course=course,
        component_tag=component_tag,
        group_codes=group_codes,
        students_number=students_number,
        placement=WeeklyPatternPlacement(
            weekday=slot.weekday,
            edits=slot.edits or [],
        ),
        start_time=slot.start_time,
        end_time=slot.end_time,
        room=slot.room,
        instructor=slot.instructor,
    )


def _meetings_from_weekly_slot_concrete(
    course: CourseConfig,
    component_tag: str,
    group_codes: tuple[str, ...],
    students_number: int | None,
    slot: WeeklyPatternSlot,
    *,
    term: TermConfig,
    audiences: list[str],
) -> list[ScheduledMeeting]:
    window = resolve_audience_semester(term, audiences)
    if window is None or (term.days and slot.weekday not in term.days):
        return []

    edits_by_week = {week_start_for_date(edit.select_week, term.starting_day): edit for edit in (slot.edits or [])}
    meetings: list[ScheduledMeeting] = []
    for pattern_date in meeting_dates_in_window(window, weekday_index(slot.weekday.value)):
        edit = edits_by_week.get(week_start_for_date(pattern_date, term.starting_day))
        if edit is not None and edit.cancel:
            continue
        meetings.append(
            _base_meeting(
                course=course,
                component_tag=component_tag,
                group_codes=group_codes,
                students_number=students_number,
                placement=OccurrencePlacement(
                    date=edit.date if edit is not None and edit.date is not None else pattern_date
                ),
                start_time=(edit.start_time if edit is not None and edit.start_time is not None else slot.start_time),
                end_time=edit.end_time if edit is not None and edit.end_time is not None else slot.end_time,
                room=edit.room if edit is not None and edit.room is not None else slot.room,
                instructor=(edit.instructor if edit is not None and edit.instructor is not None else slot.instructor),
            )
        )
    return meetings


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
                        )
                    )
                for slot in session.weekly_pattern or []:
                    if should_expand and term is not None:
                        meetings.extend(
                            _meetings_from_weekly_slot_concrete(
                                course,
                                component.tag,
                                group_codes,
                                students_number,
                                slot,
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
                            )
                        )
    return meetings
