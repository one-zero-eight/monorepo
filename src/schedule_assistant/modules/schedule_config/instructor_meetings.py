import datetime as dtm

from src.schedule_assistant.modules.issues.booking_slots import _weekday_api_value
from src.schedule_assistant.modules.issues.meetings import meeting_instructor_ids
from src.schedule_assistant.modules.schedule_config.schemas import (
    CourseConfig,
    TermConfig,
    WeeklyPatternSlotEdit,
)
from src.schedule_assistant.modules.schedule_config.semester_windows import (
    meeting_dates_in_window,
    resolve_audience_semester,
)
from src.schedule_assistant.weekday import Weekday, week_start_for_date

_API_WEEKDAY_TO_PYTHON = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _weekday_allowed(term: TermConfig, weekday: Weekday) -> bool:
    if not term.days:
        return True
    return weekday in term.days


def _meeting_dates_for_weekday(window: TermConfig.DateRange, weekday: Weekday) -> list[dtm.date]:
    """Return window dates for a weekday, stepping by weeks after the first hit."""
    target = _API_WEEKDAY_TO_PYTHON[_weekday_api_value(weekday)]
    dates = meeting_dates_in_window(window, target)
    if not dates:
        return []
    # Keep weekly stepping from first hit (same cadence as before).
    first = dates[0]
    result = [first]
    step = dtm.timedelta(days=7)
    current = first + step
    while current <= window.end_date:
        result.append(current)
        current += step
    return result


def _edits_by_week(
    edits: list[WeeklyPatternSlotEdit],
    term: TermConfig,
) -> dict[dtm.date, WeeklyPatternSlotEdit]:
    """Index edits by week start; first edit for a week wins (matches prior scan order)."""
    indexed: dict[dtm.date, WeeklyPatternSlotEdit] = {}
    for edit in edits:
        week_key = week_start_for_date(edit.select_week, term.starting_day)
        indexed.setdefault(week_key, edit)
    return indexed


def _session_audiences(component: CourseConfig.Component, session) -> list[str]:
    if session.audience:
        return list(session.audience)
    return list(component.student_groups)


def count_instructor_meetings_in_term(
    instructor_id: str,
    courses: list[CourseConfig],
    term: TermConfig | None,
) -> int:
    """Count placed semester meetings for an instructor.

    Occurrences: +1 each.
    Weekly patterns: +1 per week in the resolved audience window (unless cancelled that week).
    """
    if not instructor_id:
        return 0
    return count_meetings_by_instructor(courses, term, [instructor_id]).get(instructor_id, 0)


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
    starting_day = term.starting_day

    def bump(instructor: str | list[str] | None, amount: int = 1) -> None:
        if amount == 0:
            return
        for instructor_id in meeting_instructor_ids(instructor):
            if instructor_id in known:
                counts[instructor_id] += amount

    for course in courses:
        for component in course.components:
            for session in component.sessions or []:
                audiences = _session_audiences(component, session)
                window = resolve_audience_semester(term, audiences)
                if window is None:
                    continue

                for occurrence in session.occurrences or []:
                    bump(occurrence.instructor)

                for slot in session.weekly_pattern or []:
                    if not _weekday_allowed(term, slot.weekday):
                        continue
                    dates = _meeting_dates_for_weekday(window, slot.weekday)
                    if not dates:
                        continue
                    edits = slot.edits or []
                    if not edits:
                        bump(slot.instructor, len(dates))
                        continue

                    edits_by_week = _edits_by_week(edits, term)
                    for meeting_date in dates:
                        week_key = week_start_for_date(meeting_date, starting_day)
                        edit = edits_by_week.get(week_key)
                        if edit is not None and edit.cancel:
                            continue
                        resolved = (
                            edit.instructor if edit is not None and edit.instructor is not None else slot.instructor
                        )
                        bump(resolved)
    return counts
