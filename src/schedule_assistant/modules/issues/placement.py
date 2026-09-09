import datetime as dtm
from collections.abc import Iterator

from src.schedule_assistant.modules.issues.schemas import OccurrencePlacement, ScheduledMeeting, WeeklyPatternPlacement
from src.schedule_assistant.modules.schedule_config.schemas import TermConfig, WeeklyPatternSlot
from src.schedule_assistant.modules.schedule_config.weekly_dates import expand_weekly_slot
from src.schedule_assistant.weekday import Weekday, week_start_for_date


def _concrete_meetings(
    meeting: ScheduledMeeting,
    start_date: dtm.date,
    end_date: dtm.date,
    starting_day: Weekday,
) -> Iterator[ScheduledMeeting]:
    placement = meeting.placement
    if isinstance(placement, OccurrencePlacement):
        if start_date <= placement.date <= end_date:
            yield meeting
        return

    # A destination query must still see moves originating outside that query.
    selected_weeks = [week_start_for_date(edit.select_week, starting_day) for edit in placement.edits]
    source_start = placement.start_date or min([start_date, *selected_weeks])
    source_end = placement.end_date or max([end_date, *(week + dtm.timedelta(days=6) for week in selected_weeks)])
    slot = WeeklyPatternSlot(
        weekday=placement.weekday,
        alternation=placement.alternation,
        edits=placement.edits,
        start_time=meeting.start_time,
        end_time=meeting.end_time,
        room=meeting.room,
        instructor=meeting.instructor,
    )
    window = TermConfig.DateRange(start_date=source_start, end_date=source_end)
    for resolved in expand_weekly_slot(slot, window, starting_day):
        occurrence = resolved.occurrence
        if occurrence is None or not start_date <= occurrence.date <= end_date:
            continue
        yield meeting.model_copy(
            update={
                "placement": OccurrencePlacement(date=occurrence.date),
                "start_time": occurrence.start_time,
                "end_time": occurrence.end_time,
                "room": occurrence.room,
                "instructor": occurrence.instructor,
            }
        )


def iter_concrete_dates(
    meeting: ScheduledMeeting,
    *,
    start_date: dtm.date,
    end_date: dtm.date,
    starting_day: Weekday | None = None,
) -> Iterator[dtm.date]:
    day = starting_day or (
        meeting.placement.starting_day if isinstance(meeting.placement, WeeklyPatternPlacement) else Weekday.MONDAY
    )
    for concrete in _concrete_meetings(meeting, start_date, end_date, day):
        assert isinstance(concrete.placement, OccurrencePlacement)
        yield concrete.placement.date


def meetings_overlap(
    meeting1: ScheduledMeeting,
    meeting2: ScheduledMeeting,
    *,
    count_touching: bool = False,
    start_date: dtm.date | None = None,
    end_date: dtm.date | None = None,
    starting_day: Weekday | None = None,
) -> bool:
    # Without an explicit query, include both semester windows and moved dates.
    # Unbounded patterns repeat within 14 days; sample a cycle beyond all edits.
    bounds: list[dtm.date] = []
    unbounded = False
    for meeting in (meeting1, meeting2):
        placement = meeting.placement
        if isinstance(placement, OccurrencePlacement):
            bounds.append(placement.date)
            continue
        bounds.extend(date for date in (placement.start_date, placement.end_date) if date is not None)
        for edit in placement.edits:
            bounds.append(edit.select_week)
            if edit.date is not None:
                bounds.append(edit.date)
        unbounded |= placement.start_date is None or placement.end_date is None
    if not bounds:
        bounds = [dtm.date(2000, 1, 3)]
    query_start = start_date or min(bounds)
    query_end = end_date or (max(bounds) + dtm.timedelta(days=21) if unbounded else max(bounds))
    concrete: list[list[ScheduledMeeting]] = []
    for meeting in (meeting1, meeting2):
        day = starting_day or (
            meeting.placement.starting_day if isinstance(meeting.placement, WeeklyPatternPlacement) else Weekday.MONDAY
        )
        concrete.append(list(_concrete_meetings(meeting, query_start, query_end, day)))
    return any(
        first.placement == second.placement and _times_overlap(first, second, count_touching=count_touching)
        for first in concrete[0]
        for second in concrete[1]
    )


def _times_overlap(
    meeting1: ScheduledMeeting,
    meeting2: ScheduledMeeting,
    *,
    count_touching: bool = False,
) -> bool:
    start_a, end_a = meeting1.start_time, meeting1.end_time
    start_b, end_b = meeting2.start_time, meeting2.end_time
    if count_touching:
        return start_a <= end_b and start_b <= end_a
    return start_a < end_b and start_b < end_a


def meeting_sort_key(meeting: ScheduledMeeting) -> tuple[str | None, dtm.time]:
    placement = meeting.placement
    if isinstance(placement, OccurrencePlacement):
        return (placement.date.isoformat(), meeting.start_time)
    return (placement.weekday.value, meeting.start_time)
