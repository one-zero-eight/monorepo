import datetime as dtm
from collections.abc import Iterator

from src.schedule_assistant.modules.issues.schemas import (
    OccurrencePlacement,
    ScheduledMeeting,
    WeeklyPatternPlacement,
)
from src.schedule_assistant.modules.schedule_config.schemas import WeeklyPatternSlotEdit
from src.schedule_assistant.weekday import Weekday, week_start_for_date, weekday_index


def _edit_for_date(
    check_date: dtm.date,
    edits: list[WeeklyPatternSlotEdit],
    *,
    starting_day: Weekday = Weekday.MONDAY,
) -> WeeklyPatternSlotEdit | None:
    week_key = week_start_for_date(check_date, starting_day)
    for edit in edits:
        if week_start_for_date(edit.select_week, starting_day) == week_key:
            return edit
    return None


def _is_week_cancelled(
    check_date: dtm.date,
    edits: list[WeeklyPatternSlotEdit],
    *,
    starting_day: Weekday = Weekday.MONDAY,
) -> bool:
    edit = _edit_for_date(check_date, edits, starting_day=starting_day)
    return bool(edit and edit.cancel)


def _resolved_occurrence_date(
    pattern_date: dtm.date,
    edits: list[WeeklyPatternSlotEdit],
    *,
    starting_day: Weekday = Weekday.MONDAY,
) -> dtm.date | None:
    edit = _edit_for_date(pattern_date, edits, starting_day=starting_day)
    if edit and edit.cancel:
        return None
    if edit and edit.date is not None:
        return edit.date
    return pattern_date


def _iter_term_dates(start_date: dtm.date, end_date: dtm.date) -> Iterator[dtm.date]:
    current = start_date
    while current <= end_date:
        yield current
        current += dtm.timedelta(days=1)


def iter_concrete_dates(
    meeting: ScheduledMeeting,
    *,
    start_date: dtm.date,
    end_date: dtm.date,
    starting_day: Weekday = Weekday.MONDAY,
) -> Iterator[dtm.date]:
    placement = meeting.placement
    if isinstance(placement, OccurrencePlacement):
        if start_date <= placement.date <= end_date:
            yield placement.date
        return

    assert isinstance(placement, WeeklyPatternPlacement)
    weekday_number = weekday_index(placement.weekday.value)
    for check_date in _iter_term_dates(start_date, end_date):
        if check_date.weekday() != weekday_number:
            continue
        resolved = _resolved_occurrence_date(
            check_date,
            placement.edits,
            starting_day=starting_day,
        )
        if resolved is None:
            continue
        if start_date <= resolved <= end_date:
            yield resolved


def _occurrence_weekday(placement: OccurrencePlacement) -> int:
    return placement.date.weekday()


def _resolved_dates_for_meeting(
    meeting: ScheduledMeeting,
    *,
    start_date: dtm.date,
    end_date: dtm.date,
    starting_day: Weekday,
) -> set[dtm.date]:
    return set(
        iter_concrete_dates(
            meeting,
            start_date=start_date,
            end_date=end_date,
            starting_day=starting_day,
        )
    )


def meetings_overlap(
    meeting1: ScheduledMeeting,
    meeting2: ScheduledMeeting,
    *,
    count_touching: bool = False,
    start_date: dtm.date | None = None,
    end_date: dtm.date | None = None,
    starting_day: Weekday = Weekday.MONDAY,
) -> bool:
    placement1 = meeting1.placement
    placement2 = meeting2.placement

    # Concrete window: compare resolved dates and resolved times independently.
    # For weekly overrides this uses edit date/time when present.
    if start_date is not None and end_date is not None:
        dates1 = _resolved_dates_for_meeting(
            meeting1,
            start_date=start_date,
            end_date=end_date,
            starting_day=starting_day,
        )
        dates2 = _resolved_dates_for_meeting(
            meeting2,
            start_date=start_date,
            end_date=end_date,
            starting_day=starting_day,
        )
        if not (dates1 & dates2):
            return False
        return _times_overlap(meeting1, meeting2, count_touching=count_touching)

    if not _times_overlap(meeting1, meeting2, count_touching=count_touching):
        return False

    if isinstance(placement1, OccurrencePlacement) and isinstance(placement2, OccurrencePlacement):
        return placement1.date == placement2.date

    if isinstance(placement1, WeeklyPatternPlacement) and isinstance(placement2, WeeklyPatternPlacement):
        return placement1.weekday == placement2.weekday

    occurrence, weekly = (
        (placement1, placement2) if isinstance(placement1, OccurrencePlacement) else (placement2, placement1)
    )
    assert isinstance(occurrence, OccurrencePlacement)
    assert isinstance(weekly, WeeklyPatternPlacement)

    if _is_week_cancelled(occurrence.date, weekly.edits, starting_day=starting_day):
        return False

    weekday_number = weekday_index(weekly.weekday.value)
    # Occurrence may be a moved weekly date; match any pattern date in the same week.
    week_key = week_start_for_date(occurrence.date, starting_day)
    pattern_date = week_key + dtm.timedelta(days=(weekday_number - week_key.weekday()) % 7)
    resolved = _resolved_occurrence_date(
        pattern_date,
        weekly.edits,
        starting_day=starting_day,
    )
    if resolved == occurrence.date:
        return True
    return _occurrence_weekday(occurrence) == weekday_number and resolved == pattern_date


def _times_overlap(
    meeting1: ScheduledMeeting,
    meeting2: ScheduledMeeting,
    *,
    count_touching: bool = False,
) -> bool:
    today = dtm.date.today()
    start_a = dtm.datetime.combine(today, meeting1.start_time)
    end_a = dtm.datetime.combine(today, meeting1.end_time)
    start_b = dtm.datetime.combine(today, meeting2.start_time)
    end_b = dtm.datetime.combine(today, meeting2.end_time)
    if count_touching:
        return start_a <= end_b and start_b <= end_a
    return start_a < end_b and start_b < end_a


def meeting_sort_key(meeting: ScheduledMeeting) -> tuple[str | None, dtm.time]:
    placement = meeting.placement
    if isinstance(placement, OccurrencePlacement):
        return (placement.date.isoformat(), meeting.start_time)
    return (placement.weekday.value, meeting.start_time)
