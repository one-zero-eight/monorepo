import datetime as dtm

import pytest

from scripts.schedule_assistant.repair_semester_windows import FALL_2026_TEACHING_WINDOWS, prepare_repair
from src.schedule_assistant.core_courses.cell_to_event import convert_cell_to_event
from src.schedule_assistant.core_courses.config import Override, Target, override_matches_row, program_codes_for_row
from src.schedule_assistant.core_courses.parser import CoreCourseCell
from src.schedule_assistant.modules.bookings.match import iter_payload_occurrences
from src.schedule_assistant.modules.issues.booking_slots import build_bookable_slots
from src.schedule_assistant.modules.parser.core_courses_adapter import group_core_course_lessons
from src.schedule_assistant.modules.parser.schemas import Lesson
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    CoursesConfig,
    ScheduleConfig,
    SectionConfig,
    SectionsConfig,
    StudentsGroups,
    TermConfig,
    WeeklyPatternSlot,
)
from src.schedule_assistant.modules.schedule_config.semester_windows import (
    resolve_audience_semester,
    union_semester_window,
)
from src.schedule_assistant.modules.schedule_config.validation import validate_sections
from src.schedule_assistant.weekday import Weekday


def test_program_codes_for_row_en_and_ru() -> None:
    assert "BS_Y1_EN" in program_codes_for_row(course="BS - Year 1", sheet_name="1st block common")
    assert "BS_Y1_RU" in program_codes_for_row(course="BS - Year 1", sheet_name="Ru Programs")
    assert "BS_Y1_EN" not in program_codes_for_row(course="BS - Year 1", sheet_name="Ru Programs")


def test_override_programs_matches_en_not_ru() -> None:
    override = Override(
        programs=["BS_Y1_EN"],
        start_date=dtm.date(2026, 9, 1),
        end_date=dtm.date(2026, 12, 27),
    )
    assert override_matches_row(
        override,
        group="B26-CSE-01",
        course="BS - Year 1",
        sheet_name="1st block common",
    )
    assert not override_matches_row(
        override,
        group="B26-MFAI-01",
        course="BS - Year 1",
        sheet_name="Ru Programs",
    )


def test_cell_to_event_applies_program_override() -> None:
    target = Target(
        sheet_name="1st block common",
        start_date=dtm.date(2026, 8, 25),
        end_date=dtm.date(2026, 12, 27),
        override=[
            Override(
                programs=["BS_Y1_EN"],
                start_date=dtm.date(2026, 9, 1),
                end_date=dtm.date(2026, 12, 27),
            )
        ],
    )
    cell = CoreCourseCell(
        value=("Subject", "Teacher", "101"),
        spreadsheet_id="sheet",
        google_sheet_gid="1",
        google_sheet_name="1st block common",
        a1="B2",
    )
    event = convert_cell_to_event(
        cell,
        weekday="MONDAY",
        timeslot=(dtm.time(9, 0), dtm.time(10, 30)),
        course="BS - Year 1",
        group="B26-CSE-01",
        target=target,
        dont_care_location_string=True,
    )
    assert event is not None
    assert event.starts == dtm.date(2026, 9, 1)
    assert event.ends == dtm.date(2026, 12, 27)


def test_group_core_course_lessons_uses_window_dates() -> None:
    lessons = [
        Lesson(
            lesson_name="Math",
            lesson_class_type="lec",
            weekday="MONDAY",
            start_time=dtm.time(9, 0),
            end_time=dtm.time(10, 30),
            course_name="BS - Year 1",
            group_name="B26-CSE-01",
            source_type="core_course",
            window_start=dtm.date(2026, 9, 1),
            window_end=dtm.date(2026, 12, 27),
            spreadsheet_id="sheet",
            google_sheet_gid="1",
            google_sheet_name="1st block common",
        ),
        Lesson(
            lesson_name="Math",
            lesson_class_type="lec",
            weekday="TUESDAY",
            start_time=dtm.time(9, 0),
            end_time=dtm.time(10, 30),
            course_name="BS - Year 3",
            group_name="B24-CSE-01",
            source_type="core_course",
            window_start=dtm.date(2026, 8, 24),
            window_end=dtm.date(2026, 12, 27),
            spreadsheet_id="sheet",
            google_sheet_gid="1",
            google_sheet_name="1st block common",
        ),
    ]
    grouped = group_core_course_lessons(
        lessons,
        term_dates={"1st block common": (dtm.date(2026, 8, 25), dtm.date(2026, 12, 27))},
    )
    assert len(grouped) == 2
    by_cohort = {entry.cohort: entry for entry in grouped}
    assert by_cohort["BS - Year 1"].start_date == dtm.date(2026, 9, 1)
    assert by_cohort["BS - Year 3"].start_date == dtm.date(2026, 8, 24)


def test_validate_sections_rejects_inverted_program_semester() -> None:
    config = SectionsConfig(
        sections=[
            SectionConfig(
                code="core",
                name="Core",
                programs=[
                    SectionConfig.SectionProgram(
                        code="BS_Y1_EN",
                        name="Y1",
                        groups=["G1"],
                        semester=TermConfig.DateRange(
                            start_date=dtm.date(2026, 12, 1),
                            end_date=dtm.date(2026, 9, 1),
                        ),
                    )
                ],
            )
        ],
        students_groups=[
            StudentsGroups(
                code="G1",
            )
        ],
    )
    errors = validate_sections(config)
    assert any("semester.start_date must be on or before end_date" in error for error in errors)


def test_resolve_audience_semester_intersection_and_empty() -> None:
    term = TermConfig(
        name="Fall 2026",
        semester=TermConfig.DateRange(start_date=dtm.date(2026, 8, 25), end_date=dtm.date(2026, 12, 27)),
        sections=[
            SectionConfig(
                code="core",
                name="Core",
                programs=[
                    SectionConfig.SectionProgram(
                        code="Y1",
                        name="Y1",
                        groups=["G1"],
                        semester=TermConfig.DateRange(
                            start_date=dtm.date(2026, 9, 1),
                            end_date=dtm.date(2026, 12, 27),
                        ),
                    ),
                    SectionConfig.SectionProgram(
                        code="Y3",
                        name="Y3",
                        groups=["G3"],
                        semester=TermConfig.DateRange(
                            start_date=dtm.date(2026, 8, 24),
                            end_date=dtm.date(2026, 8, 30),
                        ),
                    ),
                ],
            )
        ],
    )
    single = resolve_audience_semester(term, ["G1"])
    assert single is not None
    assert single.start_date == dtm.date(2026, 9, 1)

    joint = resolve_audience_semester(term, ["G1", "G3"])
    assert joint is None

    bounds = union_semester_window(term)
    assert bounds.start_date == dtm.date(2026, 8, 24)
    assert bounds.end_date == dtm.date(2026, 12, 27)


def test_booking_slots_respect_program_semester() -> None:
    term = TermConfig(
        name="Fall 2026",
        semester=TermConfig.DateRange(start_date=dtm.date(2026, 8, 25), end_date=dtm.date(2026, 9, 15)),
        days=[Weekday.TUESDAY],
        sections=[
            SectionConfig(
                code="core",
                name="Core",
                programs=[
                    SectionConfig.SectionProgram(
                        code="BS_Y1_EN",
                        name="Y1",
                        groups=["B26-CSE-01"],
                        semester=TermConfig.DateRange(
                            start_date=dtm.date(2026, 9, 1),
                            end_date=dtm.date(2026, 9, 15),
                        ),
                    )
                ],
            )
        ],
    )
    sections = SectionsConfig(
        sections=term.sections,
        students_groups=[
            StudentsGroups(
                code="B26-CSE-01",
            )
        ],
    )
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Intro",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="lab",
                        audience=["B26-CSE-01"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["B26-CSE-01"],
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.TUESDAY,
                                        start_time=dtm.time(12, 40),
                                        end_time=dtm.time(14, 10),
                                        room="101",
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ]
    )
    slots = build_bookable_slots(courses, sections, term, known_room_ids={"101"})
    assert slots
    for slot in slots:
        recurrence = slot.payload.get("recurrence")
        if recurrence:
            assert recurrence["start_date"] >= "2026-09-01"
            assert recurrence["start_date"] > "2026-08-25"


def _fall_config() -> ScheduleConfig:
    return ScheduleConfig.model_validate(
        {
            "term": {
                "name": "Fall 2026",
                "semester": {"start_date": "2026-08-24", "end_date": "2026-12-27"},
                "sections": [
                    {
                        "code": "electives",
                        "name": "Electives",
                        "programs": [
                            {"code": f"Y{year}", "name": f"Y{year}", "groups": [f"G{year}"]} for year in (1, 2, 3)
                        ],
                    }
                ],
            },
            "rooms": [{"id": "209", "name": "209"}],
            "courses": [
                {
                    "name": "SPDA",
                    "section_code": "electives",
                    "components": [
                        {
                            "tag": "lab",
                            "audience": ["@Y3"],
                            "sessions": [
                                {
                                    "audience": ["@Y3"],
                                    "weekly_pattern": [
                                        {"weekday": day, "start_time": "12:40", "end_time": "14:10", "room": "209"}
                                        for day in ("FRIDAY", "SATURDAY")
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )


def test_repair_sets_three_inclusive_windows_preserves_old_range_and_spda_dates() -> None:
    original = _fall_config()
    revised, report = prepare_repair(original, {f"electives/Y{year}": year for year in (1, 2, 3)}, [])
    assert all(program.semester is None for program in original.term.sections[0].programs)
    for year, program in enumerate(revised.term.sections[0].programs, 1):
        start, end = FALL_2026_TEACHING_WINDOWS[year]
        assert program.semester is not None
        assert program.semester.start_date.isoformat() == start
        assert program.semester.end_date.isoformat() == end
    assert report["diagnostic_scan_window"] == {"start_date": "2026-08-24", "end_date": "2026-12-27"}
    sections = SectionsConfig(sections=revised.term.sections)
    slots = build_bookable_slots(CoursesConfig(courses=revised.courses), sections, revised.term, {"209"})
    assert [iter_payload_occurrences(slot.payload)[-1][0].date().isoformat() for slot in slots] == [
        "2026-12-04",
        "2026-12-05",
    ]
    intersection = resolve_audience_semester(revised.term, ["G1", "@Y3"], sections=sections)
    assert intersection is not None
    assert intersection.model_dump(mode="json") == {"start_date": "2026-09-01", "end_date": "2026-12-07"}


def test_separate_sections_override_term_sections_for_booking_dates() -> None:
    original = _fall_config()
    revised, _ = prepare_repair(original, {"electives/Y3": 3}, [])
    slots = build_bookable_slots(
        CoursesConfig(courses=revised.courses), SectionsConfig(sections=revised.term.sections), original.term, {"209"}
    )
    assert slots[0].payload["recurrence"]["until_date"] == "2026-12-04"


def test_clips_explicit_occurrences_and_edits_outside_program_window() -> None:
    revised, _ = prepare_repair(_fall_config(), {"electives/Y3": 3}, [])
    sessions = revised.courses[0].components[0].sessions
    assert sessions is not None
    session = sessions[0]
    session_data = session.model_dump(mode="json")
    session_data["weekly_pattern"][0]["edits"] = [{"select_week": "2026-12-04", "date": "2026-12-11"}]
    session_data["dates_pattern"] = [
        {"date": day, "start_time": "16:00", "end_time": "17:30", "room": "209"}
        for day in ("2026-08-23", "2026-08-24", "2026-12-07", "2026-12-08")
    ]
    sessions[0] = ComponentSessionSeries.model_validate(session_data)
    slots = build_bookable_slots(
        CoursesConfig(courses=revised.courses), SectionsConfig(sections=revised.term.sections), revised.term, {"209"}
    )
    dates = {start.date().isoformat() for slot in slots for start, _ in iter_payload_occurrences(slot.payload)}
    assert "2026-08-24" in dates and "2026-12-07" in dates
    assert not dates & {"2026-08-23", "2026-12-08", "2026-12-11", "2026-12-04"}


def test_repair_reports_excess_series_without_allowing_live_apply() -> None:
    original = _fall_config()
    own = {
        "room_id": "209",
        "title": "Auto: SPDA (lab, @Y3)",
        "categories": ["electives", "Y3", "SPDA"],
        "start": "2026-08-28T12:40:00+03:00",
        "end": "2026-08-28T14:10:00+03:00",
        "recurrence": {"weekday": "friday", "start_date": "2026-08-28", "until_date": "2026-12-25"},
        "recurrence_complete": True,
        "outlook_booking_id": "spda-master",
        "uid": "spda-uid",
        "organizer_mailbox": "organizer@example.com",
    }
    _, report = prepare_repair(original, {"electives/Y3": 3}, [own])
    series = report["series"][0]
    assert series["action"] == "propose_shorten"
    assert series["proposed_until"] == "2026-12-04"
    assert series["excess_dates"] == ["2026-12-11", "2026-12-18", "2026-12-25"]
    assert series["can_apply"] is False
    assert series["requires_exchange_validation"] is True


def test_edit_moved_from_outside_window_into_teaching_window_is_kept() -> None:
    revised, _ = prepare_repair(_fall_config(), {"electives/Y3": 3}, [])
    sessions = revised.courses[0].components[0].sessions
    assert sessions is not None
    session = sessions[0]
    data = session.model_dump(mode="json")
    data["weekly_pattern"][0]["edits"] = [{"select_week": "2026-12-11", "date": "2026-12-07"}]
    sessions[0] = ComponentSessionSeries.model_validate(data)
    slots = build_bookable_slots(
        CoursesConfig(courses=revised.courses), SectionsConfig(sections=revised.term.sections), revised.term, {"209"}
    )
    dates = {start.date().isoformat() for slot in slots for start, _ in iter_payload_occurrences(slot.payload)}
    assert "2026-12-07" in dates
    assert "2026-12-11" not in dates


@pytest.mark.parametrize("selection", [{}, {"electives/Y9": 3}, {"electives/Y3": 4}])
def test_repair_requires_reviewed_supported_program_selection(selection) -> None:
    with pytest.raises(ValueError):
        prepare_repair(_fall_config(), selection, [])
