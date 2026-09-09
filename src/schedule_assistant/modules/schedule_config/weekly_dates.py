"""Shared weekly source dates and overrides; skipped weeks never create occurrences."""

import datetime as dtm
from dataclasses import dataclass

from src.schedule_assistant.modules.schedule_config.schemas import (
    SessionOccurrence,
    TermConfig,
    WeeklyAlternation,
    WeeklyPatternSlot,
    WeeklyPatternSlotEdit,
)
from src.schedule_assistant.modules.schedule_config.semester_windows import meeting_dates_in_window
from src.schedule_assistant.weekday import Weekday, week_start_for_date


def normalize_alternation(alternation: WeeklyAlternation | None, starting_day: Weekday) -> WeeklyAlternation | None:
    if alternation is None:
        return None
    return WeeklyAlternation(anchor_week=week_start_for_date(alternation.anchor_week, starting_day))


def active_weekly_dates(
    window: TermConfig.DateRange,
    weekday: Weekday,
    starting_day: Weekday,
    alternation: WeeklyAlternation | None = None,
) -> list[dtm.date]:
    """Inclusive audience window, with phase extending both before and after the anchor."""
    dates = meeting_dates_in_window(window, weekday.index)
    if alternation is None:
        return dates
    anchor = week_start_for_date(alternation.anchor_week, starting_day)
    return [date for date in dates if (week_start_for_date(date, starting_day) - anchor).days % 14 == 0]


@dataclass(frozen=True)
class WeeklyOccurrence:
    source_date: dtm.date
    occurrence: SessionOccurrence | None
    edit: WeeklyPatternSlotEdit | None


def expand_weekly_slot(
    slot: WeeklyPatternSlot,
    window: TermConfig.DateRange,
    starting_day: Weekday,
) -> list[WeeklyOccurrence]:
    """Apply edits only to active source dates; keep cancellations as occurrence=None.

    Destination dates may be outside the source week/window. Callers selecting a
    destination window must filter after expansion, never infer new source dates.
    """
    edits = {week_start_for_date(edit.select_week, starting_day): edit for edit in slot.edits or []}
    result: list[WeeklyOccurrence] = []
    for source_date in active_weekly_dates(window, slot.weekday, starting_day, slot.alternation):
        edit = edits.get(week_start_for_date(source_date, starting_day))
        occurrence = None
        if edit is None or not edit.cancel:
            occurrence = SessionOccurrence(
                date=edit.date if edit is not None and edit.date is not None else source_date,
                start_time=edit.start_time if edit is not None and edit.start_time is not None else slot.start_time,
                end_time=edit.end_time if edit is not None and edit.end_time is not None else slot.end_time,
                room=edit.room if edit is not None and edit.room is not None else slot.room,
                instructor=edit.instructor if edit is not None and edit.instructor is not None else slot.instructor,
            )
        result.append(WeeklyOccurrence(source_date=source_date, occurrence=occurrence, edit=edit))
    return result
