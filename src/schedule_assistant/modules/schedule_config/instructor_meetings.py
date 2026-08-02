from src.schedule_assistant.modules.issues.booking_slots import (
    _edit_for_meeting_date,
    _weekly_meeting_dates_in_term,
)
from src.schedule_assistant.modules.issues.meetings import meeting_instructor_ids
from src.schedule_assistant.modules.schedule_config.schemas import (
    CourseConfig,
    TermConfig,
)
from src.schedule_assistant.weekday import Weekday


def _instructor_matches(instructor: str | list[str] | None, instructor_id: str) -> bool:
    return instructor_id in meeting_instructor_ids(instructor)


def _weekday_allowed(term: TermConfig, weekday: Weekday) -> bool:
    if not term.days:
        return True
    return weekday in term.days


def count_instructor_meetings_in_term(
    instructor_id: str,
    courses: list[CourseConfig],
    term: TermConfig | None,
) -> int:
    """Count placed semester meetings for an instructor.

    Occurrences: +1 each.
    Weekly patterns: +1 per week in the term (unless cancelled that week).
    """
    if not instructor_id or not term:
        return 0

    count = 0
    for course in courses:
        for component in course.components:
            for session in component.sessions or []:
                for occurrence in session.occurrences or []:
                    if _instructor_matches(occurrence.instructor, instructor_id):
                        count += 1

                for slot in session.weekly_pattern or []:
                    if not _weekday_allowed(term, slot.weekday):
                        continue
                    for meeting_date in _weekly_meeting_dates_in_term(term, slot.weekday):
                        edit = _edit_for_meeting_date(meeting_date, slot.edits or [], term)
                        if edit is not None and edit.cancel:
                            continue
                        resolved = (
                            edit.instructor if edit is not None and edit.instructor is not None else slot.instructor
                        )
                        if _instructor_matches(resolved, instructor_id):
                            count += 1
    return count


def count_meetings_by_instructor(
    courses: list[CourseConfig],
    term: TermConfig | None,
    instructor_ids: list[str],
) -> dict[str, int]:
    """Count meetings for many instructors in one courses walk."""
    if not term or not instructor_ids:
        return {instructor_id: 0 for instructor_id in instructor_ids}

    counts = {instructor_id: 0 for instructor_id in instructor_ids}
    known = set(instructor_ids)

    def bump(instructor: str | list[str] | None) -> None:
        for instructor_id in meeting_instructor_ids(instructor):
            if instructor_id in known:
                counts[instructor_id] += 1

    for course in courses:
        for component in course.components:
            for session in component.sessions or []:
                for occurrence in session.occurrences or []:
                    bump(occurrence.instructor)

                for slot in session.weekly_pattern or []:
                    if not _weekday_allowed(term, slot.weekday):
                        continue
                    for meeting_date in _weekly_meeting_dates_in_term(term, slot.weekday):
                        edit = _edit_for_meeting_date(meeting_date, slot.edits or [], term)
                        if edit is not None and edit.cancel:
                            continue
                        resolved = (
                            edit.instructor if edit is not None and edit.instructor is not None else slot.instructor
                        )
                        bump(resolved)
    return counts
