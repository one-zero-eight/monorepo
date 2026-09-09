import datetime as dtm
import io
from typing import Literal

import icalendar
import pytest
from openpyxl import load_workbook

from src.schedule_assistant.modules.issues.schemas import OccurrencePlacement
from src.schedule_assistant.modules.schedule.domain import meetings_from_schedule_config
from src.schedule_assistant.modules.schedule.export_xlsx import expand_meetings, export_schedule_xlsx
from src.schedule_assistant.modules.schedule.ics import render_calendar
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CoursesConfig,
    SectionsConfig,
    SessionOccurrence,
    WeeklyPatternSlotEdit,
)
from src.schedule_assistant.modules.schedule_config.weekly_dates import expand_weekly_slot
from src.schedule_assistant.modules.schedule_config.weekly_pattern_canonicalization import canonicalize_weekly_slot
from tests.schedule_assistant.test_public_timetable import seed_timetable, timetable_config


def test_notes_defaults_and_serialization() -> None:
    occurrence = SessionOccurrence(date=dtm.date(2026, 9, 7), start_time=dtm.time(9), end_time=dtm.time(10, 30))
    assert ComponentSessionSeries().notes == ""  # noqa: PLC1901 — None must not pass this contract.
    assert occurrence.notes is None
    assert WeeklyPatternSlotEdit(select_week=dtm.date(2026, 9, 7)).notes is None
    for notes in (None, "", "A note\nwith a second line"):
        with_note = occurrence.model_copy(update={"notes": notes})
        assert SessionOccurrence.model_validate_json(with_note.model_dump_json()).notes == notes
        edit = WeeklyPatternSlotEdit(select_week=dtm.date(2026, 9, 7), notes=notes)
        assert WeeklyPatternSlotEdit.model_validate_json(edit.model_dump_json()).notes == notes


def test_notes_only_edits_survive_canonicalization_and_expansion() -> None:
    config = timetable_config()
    sessions = config.courses[0].components[0].sessions
    assert sessions
    pattern = sessions[0].weekly_pattern
    assert pattern
    slot = pattern[0].model_copy(update={"alternation": None})
    dates = [dtm.date(2026, 9, day) for day in (7, 14, 21, 28)]
    notes = ["", None, "Read chapter 2", None]
    slot = slot.model_copy(
        update={
            "room": "old-room",
            "edits": [
                WeeklyPatternSlotEdit(select_week=date, room="108", notes=note)
                for date, note in zip(dates, notes, strict=True)
            ],
        }
    )
    normalized = canonicalize_weekly_slot(slot, config.term, ["G1"])
    assert normalized.room == "108"
    assert normalized.edits is not None
    assert [(edit.select_week, edit.notes) for edit in normalized.edits] == [
        (dates[0], ""),
        (dates[2], "Read chapter 2"),
    ]
    resolved_notes = []
    for resolved in expand_weekly_slot(normalized, config.term.semester, config.term.starting_day):
        assert resolved.occurrence is not None
        resolved_notes.append(resolved.occurrence.notes)
    assert resolved_notes == notes
    assert canonicalize_weekly_slot(normalized, config.term, ["G1"]) == normalized


def test_note_overrides_survive_repository_roundtrip(schedule_data_repo) -> None:
    seed_timetable(schedule_data_repo)
    series = schedule_data_repo.get_assembled().courses[0].components[0].sessions[0]
    assert series.notes == "Bring a laptop"
    assert [edit.notes for edit in series.weekly_pattern[0].edits] == ["", "Read chapter 2"]
    assert [occurrence.notes for occurrence in series.dates_pattern] == [None, "", "Read chapter 3"]


def test_concrete_and_recurring_calendars_resolve_notes() -> None:
    config = timetable_config()
    sections = SectionsConfig(sections=config.term.sections, students_groups=config.students_groups)
    courses = CoursesConfig(courses=config.courses)
    concrete = meetings_from_schedule_config(courses, sections, config.term)
    notes_by_date = {}
    for meeting in concrete:
        assert isinstance(meeting.placement, OccurrencePlacement)
        notes_by_date[meeting.placement.date] = meeting.notes
    assert notes_by_date == {
        dtm.date(2026, 9, 7): "",
        dtm.date(2026, 9, 8): "Bring a laptop",
        dtm.date(2026, 9, 15): "",
        dtm.date(2026, 9, 21): "Read chapter 2",
        dtm.date(2026, 9, 22): "Read chapter 3",
    }
    recurring = meetings_from_schedule_config(courses, sections, config.term, expand_weekly=False)
    calendar = icalendar.Calendar.from_ical(render_calendar("Timetable", [("g1", meeting) for meeting in recurring]))
    events = calendar.walk("VEVENT")
    base = next(event for event in events if event.get("RRULE"))
    assert "Bring a laptop" in str(base["DESCRIPTION"])
    overrides = {event.decoded("RECURRENCE-ID").date(): event for event in events if event.get("RECURRENCE-ID")}
    assert "Bring a laptop" not in str(overrides[dtm.date(2026, 9, 7)].get("DESCRIPTION", ""))
    assert "Read chapter 2" in str(overrides[dtm.date(2026, 9, 21)]["DESCRIPTION"])
    assert "Bring a laptop" not in str(overrides[dtm.date(2026, 9, 21)]["DESCRIPTION"])


@pytest.mark.parametrize("layout", ["groups", "compact_groups", "calendar"])
def test_xlsx_export_keeps_resolved_notes(layout: Literal["groups", "compact_groups", "calendar"]) -> None:
    config = timetable_config()
    assert [meeting.notes for meeting in expand_meetings(config)] == [
        "Bring a laptop",
        "",
        "Read chapter 3",
        "",
        "Read chapter 2",
    ]
    config.term.sections[0].default_layout = layout
    if layout != "calendar":
        # Weekly layouts intentionally show the dominant meeting for each cell.
        # Use one meeting per cell to verify notes without changing that policy.
        sessions = config.courses[0].components[0].sessions
        assert sessions
        series = sessions[0]
        assert series.weekly_pattern
        assert series.dates_pattern
        series.weekly_pattern[0].alternation = None
        series.weekly_pattern[0].edits = None
        series.dates_pattern = [series.dates_pattern[-1]]
    content, _filename = export_schedule_xlsx(config)
    workbook = load_workbook(io.BytesIO(content), rich_text=True)
    text = "\n".join(str(cell.value) for sheet in workbook for row in sheet for cell in row if cell.value is not None)
    assert "Bring a laptop" in text
    if layout == "calendar":
        assert "Read chapter 2" in text
    assert "Read chapter 3" in text
