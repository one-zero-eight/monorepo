import datetime as dtm
from collections.abc import Iterator

from src.schedule_assistant.modules.issues.schemas import (
    OccurrencePlacement,
    ScheduledMeeting,
    WeeklyPatternPlacement,
)
from src.schedule_assistant.modules.schedule_config.schemas import WeeklyPatternSlotEdit
from src.schedule_assistant.weekday import weekday_index


def _same_week(left: dtm.date, right: dtm.date) -> bool:
    return left.isocalendar()[:2] == right.isocalendar()[:2]


def _is_week_cancelled(check_date: dtm.date, edits: list[WeeklyPatternSlotEdit]) -> bool:
    return any(edit.cancel and _same_week(check_date, edit.select_week) for edit in edits)


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
        if _is_week_cancelled(check_date, placement.edits):
            continue
        yield check_date


def _occurrence_weekday(placement: OccurrencePlacement) -> int:
    return placement.date.weekday()


def meetings_overlap(
    meeting1: ScheduledMeeting,
    meeting2: ScheduledMeeting,
    *,
    count_touching: bool = False,
) -> bool:
    if not _times_overlap(meeting1, meeting2, count_touching=count_touching):
        return False

    placement1 = meeting1.placement
    placement2 = meeting2.placement

    if isinstance(placement1, OccurrencePlacement) and isinstance(placement2, OccurrencePlacement):
        return placement1.date == placement2.date

    if isinstance(placement1, WeeklyPatternPlacement) and isinstance(placement2, WeeklyPatternPlacement):
        return placement1.weekday == placement2.weekday

    occurrence, weekly = (
        (placement1, placement2) if isinstance(placement1, OccurrencePlacement) else (placement2, placement1)
    )
    assert isinstance(occurrence, OccurrencePlacement)
    assert isinstance(weekly, WeeklyPatternPlacement)

    if _occurrence_weekday(occurrence) != weekday_index(weekly.weekday.value):
        return False
    return not _is_week_cancelled(occurrence.date, weekly.edits)


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
        return placement.date.isoformat(), meeting.start_time
    return placement.weekday.value, meeting.start_time
