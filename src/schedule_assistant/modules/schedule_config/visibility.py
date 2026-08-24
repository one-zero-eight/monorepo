from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    InstructorConfig,
    SessionOccurrence,
    WeeklyPatternSlot,
)


def _normalize(value: str) -> str:
    return value.strip().casefold()


def instructor_identity_values(instructor: InstructorConfig.Instructor) -> set[str]:
    return _instructor_identity_values(instructor)


def _instructor_identity_values(instructor: InstructorConfig.Instructor) -> set[str]:
    values = {instructor.id}
    if instructor.email:
        values.add(instructor.email)
    if instructor.alias:
        values.add(instructor.alias)
    if instructor.name_en:
        values.add(instructor.name_en)
    if instructor.name_ru:
        values.add(instructor.name_ru)
    return {_normalize(value) for value in values if value}


def collect_scheduled_instructor_tokens(courses: list[CourseConfig]) -> set[str]:
    tokens: set[str] = set()
    for course in courses:
        for component in course.components:
            if not component.sessions:
                continue
            for session in component.sessions:
                if session.dates_pattern:
                    for occurrence in session.dates_pattern:
                        if occurrence.instructor is None:
                            continue
                        if isinstance(occurrence.instructor, list):
                            tokens.update(occurrence.instructor)
                        else:
                            tokens.add(occurrence.instructor)
                if session.weekly_pattern:
                    for slot in session.weekly_pattern:
                        if slot.instructor is not None:
                            if isinstance(slot.instructor, list):
                                tokens.update(slot.instructor)
                            else:
                                tokens.add(slot.instructor)
                        for edit in slot.edits or []:
                            if edit.cancel or edit.instructor is None:
                                continue
                            if isinstance(edit.instructor, list):
                                tokens.update(edit.instructor)
                            else:
                                tokens.add(edit.instructor)
    return {_normalize(token) for token in tokens if token}


def filter_scheduled_instructors(instructors: InstructorConfig, courses: list[CourseConfig]) -> InstructorConfig:
    scheduled_tokens = collect_scheduled_instructor_tokens(courses)
    if not scheduled_tokens:
        return InstructorConfig()
    filtered = [
        instructor
        for instructor in instructors.instructors
        if _instructor_identity_values(instructor) & scheduled_tokens
    ]
    return InstructorConfig(instructors=filtered)


def find_instructor_by_id(instructors: InstructorConfig, instructor_id: str) -> InstructorConfig.Instructor | None:
    normalized_id = _normalize(instructor_id)
    for instructor in instructors.instructors:
        if _normalize(instructor.id) == normalized_id:
            return instructor
    return None


def meeting_instructor_matches(instructor: str | list[str] | None, identity: set[str]) -> bool:
    if instructor is None:
        return False
    candidates = instructor if isinstance(instructor, list) else [instructor]
    return any(_normalize(candidate) in identity for candidate in candidates)


def _filter_occurrences(
    occurrences: list[SessionOccurrence] | None,
    identity: set[str],
) -> list[SessionOccurrence] | None:
    if not occurrences:
        return None
    filtered = [occurrence for occurrence in occurrences if meeting_instructor_matches(occurrence.instructor, identity)]
    return filtered or None


def _weekly_slot_matches_instructor(slot: WeeklyPatternSlot, identity: set[str]) -> bool:
    if meeting_instructor_matches(slot.instructor, identity):
        return True
    for edit in slot.edits or []:
        if edit.cancel:
            continue
        if meeting_instructor_matches(edit.instructor, identity):
            return True
    return False


def _filter_weekly_pattern(
    weekly_pattern: list[WeeklyPatternSlot] | None,
    identity: set[str],
) -> list[WeeklyPatternSlot] | None:
    if not weekly_pattern:
        return None
    filtered = [slot for slot in weekly_pattern if _weekly_slot_matches_instructor(slot, identity)]
    return filtered or None


def _filter_session_for_instructor(
    session: ComponentSessionSeries,
    identity: set[str],
) -> ComponentSessionSeries | None:
    filtered_occurrences = _filter_occurrences(session.dates_pattern, identity)
    filtered_weekly_pattern = _filter_weekly_pattern(session.weekly_pattern, identity)
    if not filtered_occurrences and not filtered_weekly_pattern:
        return None
    return session.model_copy(
        update={
            "dates_pattern": filtered_occurrences,
            "weekly_pattern": filtered_weekly_pattern,
        },
    )


def filter_courses_for_instructor(courses: list[CourseConfig], identity: set[str]) -> list[CourseConfig]:
    filtered_courses: list[CourseConfig] = []
    for course in courses:
        filtered_components: list[CourseConfig.Component] = []
        for component in course.components:
            if not component.sessions:
                continue
            matching_sessions = [
                filtered_session
                for session in component.sessions
                if (filtered_session := _filter_session_for_instructor(session, identity)) is not None
            ]
            if not matching_sessions:
                continue
            filtered_components.append(component.model_copy(update={"sessions": matching_sessions}))
        if filtered_components:
            filtered_courses.append(course.model_copy(update={"components": filtered_components}))
    return filtered_courses
