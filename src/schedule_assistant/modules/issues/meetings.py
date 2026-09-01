from src.schedule_assistant.modules.issues.issue_text import attach_issue_text
from src.schedule_assistant.modules.issues.schemas import (
    IssueTypeEnum,
    MissingInstructorIssue,
    MissingRoomIssue,
    ScheduledMeeting,
    UnplacedIssue,
)
from src.schedule_assistant.modules.schedule import domain as schedule_domain
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CoursesConfig,
    InstructorConfig,
    SectionsConfig,
)
from src.schedule_assistant.modules.schedule_config.validation import build_selector_map, expand_group_tokens

meetings_from_schedule_config = schedule_domain.meetings_from_schedule_config


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


def meeting_instructor_ids(instructor: str | list[str] | None) -> list[str]:
    if instructor is None:
        return []
    if isinstance(instructor, list):
        return [value.strip() for value in instructor if value and value.strip()]
    stripped = instructor.strip()
    return [stripped] if stripped else []


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
