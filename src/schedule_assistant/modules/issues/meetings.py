import datetime as dtm

from src.schedule_assistant.modules.issues.issue_text import attach_issue_text
from src.schedule_assistant.modules.issues.schemas import (
    IssueTypeEnum,
    MissingInstructorIssue,
    MissingRoomIssue,
    OccurrencePlacement,
    ScheduledMeeting,
    UnplacedIssue,
    WeeklyPatternPlacement,
)
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    CoursesConfig,
    InstructorConfig,
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


def _normalize(value: str) -> str:
    return value.strip().casefold()


def _group_codes_for_session(
    component_groups: list[str],
    session: ComponentSessionSeries,
    selector_map: dict[str, set[str]],
) -> tuple[str, ...]:
    tokens = session.audience or component_groups
    expanded = expand_group_tokens(tokens, selector_map)
    return tuple(sorted(expanded))


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


def meeting_instructor_ids(instructor: str | list[str] | None) -> list[str]:
    if instructor is None:
        return []
    if isinstance(instructor, list):
        return [value.strip() for value in instructor if value and value.strip()]
    stripped = instructor.strip()
    return [stripped] if stripped else []


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
    if window is None:
        return []
    if term.days and slot.weekday not in term.days:
        return []

    pattern_dates = meeting_dates_in_window(window, weekday_index(slot.weekday.value))
    if not pattern_dates:
        return []

    edits = slot.edits or []
    edits_by_week = {week_start_for_date(edit.select_week, term.starting_day): edit for edit in edits}
    meetings: list[ScheduledMeeting] = []
    for pattern_date in pattern_dates:
        edit = edits_by_week.get(week_start_for_date(pattern_date, term.starting_day))
        if edit is not None and edit.cancel:
            continue
        resolved_date = edit.date if edit is not None and edit.date is not None else pattern_date
        resolved_start = edit.start_time if edit is not None and edit.start_time is not None else slot.start_time
        resolved_end = edit.end_time if edit is not None and edit.end_time is not None else slot.end_time
        resolved_room = edit.room if edit is not None and edit.room is not None else slot.room
        resolved_instructor = edit.instructor if edit is not None and edit.instructor is not None else slot.instructor
        meetings.append(
            _base_meeting(
                course=course,
                component_tag=component_tag,
                group_codes=group_codes,
                students_number=students_number,
                placement=OccurrencePlacement(date=resolved_date),
                start_time=resolved_start,
                end_time=resolved_end,
                room=resolved_room,
                instructor=resolved_instructor,
            )
        )
    return meetings


def build_group_to_studying_teachers(
    sections: SectionsConfig,
    instructors: InstructorConfig,
) -> dict[str, list[str]]:
    instructor_ids_by_identity: dict[str, str] = {}
    for instructor in instructors.instructors:
        instructor_ids_by_identity[_normalize(instructor.id)] = instructor.id
        if instructor.email:
            instructor_ids_by_identity[_normalize(instructor.email)] = instructor.id

    group_to_teachers: dict[str, list[str]] = {}
    for group in sections.students_groups:
        studying: list[str] = []
        for student in group.students:
            instructor_id = instructor_ids_by_identity.get(_normalize(student))
            if instructor_id is not None and instructor_id not in studying:
                studying.append(instructor_id)
        if studying:
            group_to_teachers[group.code] = studying
    return group_to_teachers


def meetings_from_schedule_config(
    courses: CoursesConfig,
    sections: SectionsConfig,
    term: TermConfig | None = None,
    *,
    expand_weekly: bool | None = None,
) -> list[ScheduledMeeting]:
    """Build scheduled meetings from courses.

    When ``term`` is provided (or ``expand_weekly=True``), weekly slots are expanded into
    concrete dated occurrences with overrides/cancellations applied.
    """
    selector_map = build_selector_map(sections)
    should_expand = expand_weekly if expand_weekly is not None else term is not None
    meetings: list[ScheduledMeeting] = []

    for course in courses.courses:
        for component in course.components:
            if not component.sessions:
                continue
            component_groups = component.audience
            for session in component.sessions:
                group_codes = _group_codes_for_session(component_groups, session, selector_map)
                students_number = component.expected_enrollment
                if students_number is None:
                    students_number = _enrollment_size(group_codes, sections)
                audiences = list(session.audience or component_groups)

                if session.dates_pattern:
                    for occurrence in session.dates_pattern:
                        meetings.append(
                            _meeting_from_occurrence(
                                course,
                                component.tag,
                                group_codes,
                                students_number,
                                occurrence,
                            ),
                        )
                if session.weekly_pattern:
                    for slot in session.weekly_pattern:
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
                                ),
                            )

    return meetings


def _session_is_placed(session: ComponentSessionSeries) -> bool:
    return bool(session.weekly_pattern) or bool(session.dates_pattern)


def unplaced_issues_from_schedule_config(courses: CoursesConfig, sections: SectionsConfig) -> list[UnplacedIssue]:
    selector_map = build_selector_map(sections)
    issues: list[UnplacedIssue] = []

    for course in courses.courses:
        for component in course.components:
            sessions = component.sessions or []
            if not sessions:
                group_codes = tuple(sorted(expand_group_tokens(component.audience, selector_map)))
                issue = UnplacedIssue(
                    issue_type=IssueTypeEnum.UNPLACED,
                    course_name=course.name,
                    component_tag=component.tag,
                    student_groups=group_codes,
                )
                attach_issue_text(issue)
                issues.append(issue)
                continue

            for session in sessions:
                if _session_is_placed(session):
                    continue
                group_codes = _group_codes_for_session(component.audience, session, selector_map)
                issue = UnplacedIssue(
                    issue_type=IssueTypeEnum.UNPLACED,
                    course_name=course.name,
                    component_tag=component.tag,
                    student_groups=group_codes,
                )
                attach_issue_text(issue)
                issues.append(issue)

    return issues


def _blank_room(room: str | None) -> bool:
    return not (room or "").strip()


def missing_assignment_issues_from_meetings(
    meetings: list[ScheduledMeeting],
) -> list[MissingRoomIssue | MissingInstructorIssue]:
    issues: list[MissingRoomIssue | MissingInstructorIssue] = []
    for meeting in meetings:
        if _blank_room(meeting.room):
            issue = MissingRoomIssue(
                issue_type=IssueTypeEnum.MISSING_ROOM,
                meeting=meeting,
            )
            attach_issue_text(issue)
            issues.append(issue)
        if not meeting_instructor_ids(meeting.instructor):
            issue = MissingInstructorIssue(
                issue_type=IssueTypeEnum.MISSING_INSTRUCTOR,
                meeting=meeting,
            )
            attach_issue_text(issue)
            issues.append(issue)
    return issues
