from fastapi import HTTPException, status

from src.schedule_assistant.modules.schedule_config.repository import schedule_config_repository
from src.schedule_assistant.modules.schedule_config.schemas import (
    CourseConfig,
    CoursesConfig,
    SectionsConfig,
    StudentsGroups,
)
from src.schedule_assistant.modules.schedule_config.visibility import (
    filter_courses_for_instructor,
    find_instructor_by_id,
)


def _normalize_email(email: str) -> str:
    return email.strip().casefold()


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
