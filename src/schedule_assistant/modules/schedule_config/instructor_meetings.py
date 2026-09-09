from src.schedule_assistant.modules.issues.meetings import meeting_instructor_ids
from src.schedule_assistant.modules.schedule_config.schemas import CourseConfig, TermConfig
from src.schedule_assistant.modules.schedule_config.semester_windows import resolve_audience_semester
from src.schedule_assistant.modules.schedule_config.weekly_dates import expand_weekly_slot


def count_instructor_meetings_in_term(
    instructor_id: str,
    courses: list[CourseConfig],
    term: TermConfig | None,
) -> int:
    """Count actual placed meetings, including active weekly edits and cancellations."""
    if not instructor_id:
        return 0
    return count_meetings_by_instructor(courses, term, [instructor_id]).get(instructor_id, 0)


def count_meetings_by_instructor(
    courses: list[CourseConfig],
    term: TermConfig | None,
    instructor_ids: list[str],
) -> dict[str, int]:
    """Count meetings for many instructors in one courses walk."""
    counts = dict.fromkeys(instructor_ids, 0)
    if term is None or not instructor_ids:
        return counts

    def bump(instructor: str | list[str] | None) -> None:
        for instructor_id in meeting_instructor_ids(instructor):
            if instructor_id in counts:
                counts[instructor_id] += 1

    for course in courses:
        for component in course.components:
            for session in component.sessions or []:
                window = resolve_audience_semester(term, list(session.audience or component.audience))
                if window is None:
                    continue
                for occurrence in session.dates_pattern or []:
                    bump(occurrence.instructor)
                for slot in session.weekly_pattern or []:
                    if term.days and slot.weekday not in term.days:
                        continue
                    for resolved in expand_weekly_slot(slot, window, term.starting_day):
                        if resolved.occurrence is not None:
                            bump(resolved.occurrence.instructor)
    return counts
