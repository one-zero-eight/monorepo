import datetime as dtm

from src.schedule_assistant.core_courses.cell_to_event import convert_cell_to_event
from src.schedule_assistant.core_courses.config import Override, Target, override_matches_row, program_codes_for_row
from src.schedule_assistant.core_courses.parser import CoreCourseCell
from src.schedule_assistant.modules.issues.booking_slots import build_bookable_slots
from src.schedule_assistant.modules.parser.core_courses_adapter import group_core_course_lessons
from src.schedule_assistant.modules.parser.schemas import Lesson
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    CoursesConfig,
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
        students_groups=[StudentsGroups(code="G1", kind="core")],
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
        students_groups=[StudentsGroups(code="B26-CSE-01", kind="core")],
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
