import datetime as dtm
from collections.abc import Sequence
from typing import Literal

from src.schedule_assistant.modules.issues.issue_text import attach_issue_text
from src.schedule_assistant.modules.issues.schemas import (
    IssueTypeEnum,
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
    WeeklyPatternSlot,
)
from src.schedule_assistant.modules.schedule_config.validation import build_selector_map, expand_group_tokens


def _normalize(value: str) -> str:
    return value.strip().casefold()


def build_token_to_section_kind(sections: SectionsConfig) -> dict[str, str]:
    """Map group codes and @selectors to section.kind (or students_groups.kind fallback)."""
    token_to_kind: dict[str, str] = {}
    for section in sections.sections:
        kind = str(section.kind or section.code or "").strip().lower()
        if not kind:
            continue
        for program in section.programs:
            token_to_kind[f"@{program.code}"] = kind
            for group in program.groups:
                token_to_kind[group] = kind
            for track in program.tracks:
                token_to_kind[f"@{program.code}/{track.name}"] = kind
                token_to_kind[f"@{program.code}/{track.code}"] = kind
                for group in track.groups:
                    token_to_kind[group] = kind
    for group in sections.students_groups:
        code = group.code.strip()
        kind = str(group.kind or "").strip().lower()
        if code and kind and code not in token_to_kind:
            token_to_kind[code] = kind
    return token_to_kind


def resolve_section_kind(
    audiences: Sequence[str],
    token_to_kind: dict[str, str],
) -> str | None:
    for audience in audiences:
        token = audience.strip()
        if not token:
            continue
        kind = token_to_kind.get(token)
        if kind is not None:
            return kind
        if token.startswith("@") and "/" in token:
            program_token = token.split("/", 1)[0]
            kind = token_to_kind.get(program_token)
            if kind is not None:
                return kind
    return None


def booking_section_category(section_kind: str | None) -> str:
    if section_kind is None:
        return "unknown"
    if section_kind in ("core", "core_course"):
        return "core"
    if section_kind in ("electives", "elective"):
        return "elective"
    if section_kind == "english":
        return "english"
    return section_kind


def source_kind_from_section_kind(
    section_kind: str | None,
) -> Literal["core_course", "elective"]:
    if section_kind in ("core", "core_course"):
        return "core_course"
    return "elective"


def source_kind_from_audiences(
    audiences: Sequence[str],
    token_to_kind: dict[str, str],
) -> Literal["core_course", "elective"]:
    return source_kind_from_section_kind(resolve_section_kind(audiences, token_to_kind))


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
        return [value for value in instructor if value]
    return [instructor]


def _base_meeting(
    *,
    course: CourseConfig,
    component_tag: str,
    source_kind: Literal["core_course", "elective"],
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
        source_kind=source_kind,
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
    source_kind: Literal["core_course", "elective"],
    group_codes: tuple[str, ...],
    students_number: int | None,
    occurrence: SessionOccurrence,
) -> ScheduledMeeting:
    return _base_meeting(
        course=course,
        component_tag=component_tag,
        source_kind=source_kind,
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
    source_kind: Literal["core_course", "elective"],
    group_codes: tuple[str, ...],
    students_number: int | None,
    slot: WeeklyPatternSlot,
) -> ScheduledMeeting:
    return _base_meeting(
        course=course,
        component_tag=component_tag,
        source_kind=source_kind,
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


def meetings_from_schedule_config(courses: CoursesConfig, sections: SectionsConfig) -> list[ScheduledMeeting]:
    selector_map = build_selector_map(sections)
    token_to_kind = build_token_to_section_kind(sections)
    meetings: list[ScheduledMeeting] = []

    for course in courses.courses:
        for component in course.components:
            if not component.sessions:
                continue
            component_groups = component.student_groups
            for session in component.sessions:
                audience_tokens = session.audience or component_groups
                source_kind = source_kind_from_audiences(audience_tokens, token_to_kind)
                group_codes = _group_codes_for_session(component_groups, session, selector_map)
                students_number = component.expected_enrollment
                if students_number is None:
                    students_number = _enrollment_size(group_codes, sections)

                if session.occurrences:
                    for occurrence in session.occurrences:
                        meetings.append(
                            _meeting_from_occurrence(
                                course,
                                component.tag,
                                source_kind,
                                group_codes,
                                students_number,
                                occurrence,
                            ),
                        )
                if session.weekly_pattern:
                    for slot in session.weekly_pattern:
                        meetings.append(
                            _meeting_from_weekly_slot(
                                course,
                                component.tag,
                                source_kind,
                                group_codes,
                                students_number,
                                slot,
                            ),
                        )

    return meetings


def _session_is_placed(session: ComponentSessionSeries) -> bool:
    return bool(session.weekly_pattern) or bool(session.occurrences)


def unplaced_issues_from_schedule_config(courses: CoursesConfig, sections: SectionsConfig) -> list[UnplacedIssue]:
    selector_map = build_selector_map(sections)
    token_to_kind = build_token_to_section_kind(sections)
    issues: list[UnplacedIssue] = []

    for course in courses.courses:
        for component in course.components:
            sessions = component.sessions or []
            if not sessions:
                group_codes = tuple(sorted(expand_group_tokens(component.student_groups, selector_map)))
                issue = UnplacedIssue(
                    issue_type=IssueTypeEnum.UNPLACED,
                    course_name=course.name,
                    component_tag=component.tag,
                    source_kind=source_kind_from_audiences(component.student_groups, token_to_kind),
                    student_groups=group_codes,
                )
                attach_issue_text(issue)
                issues.append(issue)
                continue

            for session in sessions:
                if _session_is_placed(session):
                    continue
                audience_tokens = session.audience or component.student_groups
                group_codes = _group_codes_for_session(component.student_groups, session, selector_map)
                issue = UnplacedIssue(
                    issue_type=IssueTypeEnum.UNPLACED,
                    course_name=course.name,
                    component_tag=component.tag,
                    source_kind=source_kind_from_audiences(audience_tokens, token_to_kind),
                    student_groups=group_codes,
                )
                attach_issue_text(issue)
                issues.append(issue)

    return issues
