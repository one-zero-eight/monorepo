from fastapi import HTTPException, status

from src.schedule_assistant.config import settings
from src.schedule_assistant.modules.issues.schemas import ScheduledMeeting
from src.schedule_assistant.modules.schedule.domain import meetings_from_schedule_config
from src.schedule_assistant.modules.schedule.export_xlsx import export_schedule_xlsx as build_schedule_xlsx
from src.schedule_assistant.modules.schedule.ics import group_alias, render_calendar, teacher_alias
from src.schedule_assistant.modules.schedule.schemas import VirtualEventGroup
from src.schedule_assistant.modules.schedule_config.repository import schedule_config_repository
from src.schedule_assistant.modules.schedule_config.schemas import (
    CourseConfig,
    CoursesConfig,
    InstructorConfig,
    SectionsConfig,
    StudentsGroups,
)
from src.schedule_assistant.modules.schedule_config.visibility import (
    filter_courses_for_instructor,
    filter_scheduled_instructors,
    find_instructor_by_email,
    find_instructor_by_id,
    instructor_identity_values,
    meeting_instructor_matches,
)


def _normalize_email(email: str) -> str:
    return email.strip().casefold()


def _published_kind(kind: str) -> bool:
    if settings.published_group_kinds is None:
        return True
    published = {_normalize_email(value) for value in settings.published_group_kinds}
    return _normalize_email(kind) in published


def _instructor_name(instructor: InstructorConfig.Instructor) -> str:
    return (
        (instructor.name_en or "").strip()
        or (instructor.name_ru or "").strip()
        or (instructor.email or "").strip()
        or instructor.id
    )


def list_virtual_event_groups() -> list[VirtualEventGroup]:
    student_groups = [
        VirtualEventGroup(
            alias=group_alias(group.kind, group.code),
            name=group.name or group.code,
            description=f"Schedule for {group.name or group.code}",
            kind=group.kind,
            group_code=group.code,
        )
        for group in schedule_config_repository.get_sections().students_groups
        if _published_kind(group.kind)
    ]
    instructors = filter_scheduled_instructors(
        schedule_config_repository.get_instructors(),
        schedule_config_repository.get_courses().courses,
    ).instructors
    instructor_groups = [
        VirtualEventGroup(
            alias=teacher_alias(instructor.email),
            name=_instructor_name(instructor),
            description=f"Schedule for {_instructor_name(instructor)}",
            kind="instructor",
            instructor_id=instructor.id,
        )
        for instructor in instructors
        if instructor.email and instructor.email.strip()
    ]
    groups = student_groups + instructor_groups
    aliases = [group.alias for group in groups]
    if len(aliases) != len(set(aliases)):
        raise RuntimeError("Virtual event group aliases must be unique")
    groups.sort(key=lambda group: group.alias)
    return groups


def get_predefined_aliases(user_email: str) -> list[str]:
    normalized_email = _normalize_email(user_email)
    aliases = [
        group_alias(group.kind, group.code)
        for group in schedule_config_repository.get_sections().students_groups
        if _published_kind(group.kind)
        and any(_normalize_email(student) == normalized_email for student in group.students)
    ]
    scheduled_instructors = filter_scheduled_instructors(
        schedule_config_repository.get_instructors(),
        schedule_config_repository.get_courses().courses,
    )
    instructor = find_instructor_by_email(scheduled_instructors, user_email)
    if instructor is not None and instructor.email:
        aliases.append(teacher_alias(instructor.email))
    return sorted(set(aliases))


def _group_by_alias(alias: str) -> VirtualEventGroup:
    for group in list_virtual_event_groups():
        if group.alias == alias:
            return group
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event group not found")


def _concrete_meetings() -> list[ScheduledMeeting]:
    term = schedule_config_repository.get_term()
    if term is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule term config is required for calendar export",
        )
    return meetings_from_schedule_config(
        schedule_config_repository.get_courses(),
        schedule_config_repository.get_sections(),
        term=term,
    )


def _instructor_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for instructor in schedule_config_repository.get_instructors().instructors:
        label = (instructor.name_en or instructor.name_ru or "").strip()
        if not label:
            continue
        for identifier in (instructor.id, instructor.email, instructor.alias):
            if identifier and identifier.strip():
                names[identifier.strip().casefold()] = label
    return names


def get_group_ics(alias: str) -> bytes:
    group = _group_by_alias(alias)
    meetings = [meeting for meeting in _concrete_meetings() if _meeting_matches_group(meeting, group)]
    return render_calendar(
        group.name,
        [(alias, meeting) for meeting in meetings],
        instructor_names=_instructor_names(),
    )


def _meeting_matches_group(
    meeting: ScheduledMeeting,
    group: VirtualEventGroup,
) -> bool:
    if group.group_code is not None:
        return group.group_code in meeting.groups
    if group.instructor_id is None:
        return False
    instructor = find_instructor_by_id(
        schedule_config_repository.get_instructors(),
        group.instructor_id,
    )
    if instructor is None:
        return False
    return meeting_instructor_matches(
        meeting.instructor,
        instructor_identity_values(instructor),
    )


def _meeting_identity(meeting: ScheduledMeeting) -> tuple[object, ...]:
    placement = meeting.placement
    return (
        meeting.course_name,
        meeting.component_tag,
        getattr(placement, "date", None),
        meeting.start_time.replace(tzinfo=None),
        meeting.end_time.replace(tzinfo=None),
        meeting.room,
        tuple(meeting.instructor) if isinstance(meeting.instructor, list) else meeting.instructor,
        tuple(meeting.groups),
    )


def get_aliases_ics(aliases: list[str]) -> bytes:
    normalized_aliases = sorted(set(aliases))
    groups = {alias: _group_by_alias(alias) for alias in normalized_aliases}
    meetings = _concrete_meetings()
    alias_meetings: list[tuple[str, ScheduledMeeting]] = []
    seen_meetings: set[tuple[object, ...]] = set()
    for alias, group in groups.items():
        for meeting in meetings:
            if not _meeting_matches_group(meeting, group):
                continue
            identity = _meeting_identity(meeting)
            if identity in seen_meetings:
                continue
            seen_meetings.add(identity)
            alias_meetings.append((alias, meeting))
    return render_calendar(
        "Schedule Assistant",
        alias_meetings,
        instructor_names=_instructor_names(),
    )


def _build_selector_map(sections: SectionsConfig) -> dict[str, set[str]]:
    selector_map: dict[str, set[str]] = {}
    for section in sections.sections:
        for program in section.programs:
            program_groups: set[str] = set(program.groups)
            for track in program.tracks:
                if track.groups:
                    groups = set(track.groups)
                    selector_map[f"@{program.code}/{track.name}"] = groups
                    program_groups.update(groups)
            if program_groups:
                selector_map[f"@{program.code}"] = program_groups
    return selector_map


def _expand_audience(audience: list[str], selector_map: dict[str, set[str]]) -> set[str]:
    expanded: set[str] = set()
    for token in audience:
        if token in selector_map:
            expanded.update(selector_map[token])
        else:
            expanded.add(token)
    return expanded


def _audience_matches_group(audience: list[str], group_code: str, selector_map: dict[str, set[str]]) -> bool:
    return group_code in _expand_audience(audience, selector_map)


def get_my_groups(user_email: str) -> list[StudentsGroups]:
    sections = schedule_config_repository.get_sections()
    normalized_email = _normalize_email(user_email)
    groups = [
        student_group
        for student_group in sections.students_groups
        if any(_normalize_email(student) == normalized_email for student in student_group.students)
    ]
    groups.sort(key=lambda group: group.code)
    return groups


def _filter_courses_for_group(
    courses: list[CourseConfig],
    group_code: str,
    selector_map: dict[str, set[str]],
) -> list[CourseConfig]:
    filtered_courses: list[CourseConfig] = []
    for course in courses:
        filtered_components: list[CourseConfig.Component] = []
        for component in course.components:
            if not component.sessions:
                continue
            matching_sessions = [
                session
                for session in component.sessions
                if _audience_matches_group(session.audience, group_code, selector_map)
            ]
            if not matching_sessions:
                continue
            filtered_components.append(component.model_copy(update={"sessions": matching_sessions}))
        if filtered_components:
            filtered_courses.append(course.model_copy(update={"components": filtered_components}))
    return filtered_courses


def _group_exists(group_code: str, sections: SectionsConfig, selector_map: dict[str, set[str]]) -> bool:
    known_groups = {student_group.code for student_group in sections.students_groups}
    if group_code in known_groups:
        return True
    return any(group_code in groups for groups in selector_map.values())


def get_group_schedule(group_code: str) -> CoursesConfig:
    sections = schedule_config_repository.get_sections()
    courses = schedule_config_repository.get_courses().courses
    selector_map = _build_selector_map(sections)

    if not _group_exists(group_code, sections, selector_map):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    return CoursesConfig(courses=_filter_courses_for_group(courses, group_code, selector_map))


def get_instructor_schedule(instructor_id: str) -> CoursesConfig:
    instructors = schedule_config_repository.get_instructors()
    instructor = find_instructor_by_id(instructors, instructor_id)
    if instructor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found")

    courses = schedule_config_repository.get_courses().courses
    return CoursesConfig(
        courses=filter_courses_for_instructor(courses, {_normalize_email(instructor.id)}),
    )


def export_schedule_xlsx() -> tuple[bytes, str]:
    config = schedule_config_repository.get_assembled()
    return build_schedule_xlsx(config)
