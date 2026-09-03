import datetime as dtm

from src.schedule_assistant.modules.issues.placement import meetings_overlap
from src.schedule_assistant.modules.issues.schemas import OccurrencePlacement, ScheduledMeeting, WeeklyPatternPlacement
from src.schedule_assistant.modules.schedule.domain import meetings_from_schedule_config
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    CoursesConfig,
    InstructorConfig,
    RoomConfig,
    SectionConfig,
    SectionsConfig,
    StudentsGroups,
    TermConfig,
    TermTimeSlot,
    WeeklyPatternSlot,
    WeeklyPatternSlotEdit,
)
from src.schedule_assistant.modules.schedule_config.validation import ValidationContext, validate_courses
from src.schedule_assistant.modules.schedule_config.visibility import (
    filter_courses_for_instructor,
    filter_scheduled_instructors,
    instructor_identity_values,
)
from src.schedule_assistant.weekday import Weekday


def _term() -> TermConfig:
    return TermConfig(
        name="Fall 2026",
        semester=TermConfig.DateRange(
            start_date=dtm.date(2026, 9, 1),
            end_date=dtm.date(2026, 9, 28),
        ),
        days=[Weekday.MONDAY, Weekday.TUESDAY, Weekday.WEDNESDAY, Weekday.THURSDAY, Weekday.FRIDAY],
        starting_day=Weekday.MONDAY,
        time_slots=[TermTimeSlot(start_time=dtm.time(9, 0), end_time=dtm.time(10, 30))],
        sections=[
            SectionConfig(
                code="core",
                name="Core",
                programs=[SectionConfig.SectionProgram(code="BS", name="BS", groups=["G1"])],
            )
        ],
    )


def _sections() -> SectionsConfig:
    return SectionsConfig(
        sections=_term().sections,
        students_groups=[
            StudentsGroups(
                code="G1",
            )
        ],
    )


def _ctx() -> ValidationContext:
    return ValidationContext(
        sections=_sections(),
        rooms=RoomConfig(rooms=[RoomConfig.Room(id="108", name="108"), RoomConfig.Room(id="107", name="107")]),
        instructors=InstructorConfig(
            instructors=[
                InstructorConfig.Instructor(id="a@iu.ru"),
                InstructorConfig.Instructor(id="b@iu.ru"),
            ],
        ),
        courses=CoursesConfig(),
        term=_term(),
    )


def test_validate_rejects_duplicate_select_week() -> None:
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Course",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        audience=["G1"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["G1"],
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.MONDAY,
                                        start_time=dtm.time(9, 0),
                                        end_time=dtm.time(10, 30),
                                        room="108",
                                        instructor="a@iu.ru",
                                        edits=[
                                            WeeklyPatternSlotEdit(
                                                select_week=dtm.date(2026, 9, 7),
                                                room="107",
                                            ),
                                            WeeklyPatternSlotEdit(
                                                select_week=dtm.date(2026, 9, 9),
                                                instructor="b@iu.ru",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    errors = validate_courses(courses, _ctx())
    assert any("duplicate select_week" in error for error in errors)


def test_validate_rejects_cancel_with_overrides_and_invalid_resolved_time() -> None:
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Course",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        audience=["G1"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["G1"],
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.MONDAY,
                                        start_time=dtm.time(9, 0),
                                        end_time=dtm.time(10, 30),
                                        room="108",
                                        instructor="a@iu.ru",
                                        edits=[
                                            WeeklyPatternSlotEdit(
                                                select_week=dtm.date(2026, 9, 7),
                                                cancel=True,
                                                room="107",
                                            ),
                                            WeeklyPatternSlotEdit(
                                                select_week=dtm.date(2026, 9, 14),
                                                start_time=dtm.time(12, 0),
                                                end_time=dtm.time(11, 0),
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    errors = validate_courses(courses, _ctx())
    assert any("cancel cannot be combined" in error for error in errors)
    assert any("resolved start_time must be before end_time" in error for error in errors)


def test_meetings_expand_weekly_overrides_and_cancellations() -> None:
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Course",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        audience=["G1"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["G1"],
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.MONDAY,
                                        start_time=dtm.time(9, 0),
                                        end_time=dtm.time(10, 30),
                                        room="108",
                                        instructor="a@iu.ru",
                                        edits=[
                                            WeeklyPatternSlotEdit(
                                                select_week=dtm.date(2026, 9, 14),
                                                cancel=True,
                                            ),
                                            WeeklyPatternSlotEdit(
                                                select_week=dtm.date(2026, 9, 21),
                                                date=dtm.date(2026, 9, 22),
                                                start_time=dtm.time(10, 40),
                                                end_time=dtm.time(12, 10),
                                                room="107",
                                                instructor="b@iu.ru",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    meetings = meetings_from_schedule_config(courses, _sections(), term=_term())
    assert len(meetings) == 3
    moved = next(
        meeting
        for meeting in meetings
        if isinstance(meeting.placement, OccurrencePlacement) and meeting.placement.date == dtm.date(2026, 9, 22)
    )
    assert moved.start_time == dtm.time(10, 40)
    assert moved.room == "107"
    assert moved.instructor == "b@iu.ru"
    assert all(
        not (isinstance(meeting.placement, OccurrencePlacement) and meeting.placement.date == dtm.date(2026, 9, 14))
        for meeting in meetings
    )


def test_meetings_overlap_detects_moved_weekly_occurrence() -> None:
    weekly = ScheduledMeeting(
        course_name="A",
        component_tag="lec",
        placement=WeeklyPatternPlacement(
            weekday=Weekday.MONDAY,
            edits=[
                WeeklyPatternSlotEdit(
                    select_week=dtm.date(2026, 9, 21),
                    date=dtm.date(2026, 9, 22),
                ),
            ],
        ),
        start_time=dtm.time(9, 0),
        end_time=dtm.time(10, 30),
        room="108",
        instructor="a@iu.ru",
        groups=("G1",),
    )
    occurrence = ScheduledMeeting(
        course_name="B",
        component_tag="lec",
        placement=OccurrencePlacement(date=dtm.date(2026, 9, 22)),
        start_time=dtm.time(9, 0),
        end_time=dtm.time(10, 30),
        room="108",
        instructor="b@iu.ru",
        groups=("G1",),
    )
    assert meetings_overlap(
        weekly,
        occurrence,
        start_date=dtm.date(2026, 9, 1),
        end_date=dtm.date(2026, 9, 28),
    )


def test_visibility_includes_edit_only_instructor() -> None:
    instructors = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(id="a@iu.ru"),
            InstructorConfig.Instructor(id="b@iu.ru"),
        ],
    )
    courses = [
        CourseConfig(
            name="Course",
            section_code="core",
            components=[
                CourseConfig.Component(
                    tag="lec",
                    sessions=[
                        ComponentSessionSeries(
                            weekly_pattern=[
                                WeeklyPatternSlot(
                                    weekday=Weekday.MONDAY,
                                    start_time=dtm.time(9, 0),
                                    end_time=dtm.time(10, 30),
                                    instructor="a@iu.ru",
                                    edits=[
                                        WeeklyPatternSlotEdit(
                                            select_week=dtm.date(2026, 9, 7),
                                            instructor="b@iu.ru",
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ]
    filtered = filter_scheduled_instructors(instructors, courses)
    assert {instructor.id for instructor in filtered.instructors} == {"a@iu.ru", "b@iu.ru"}

    identity = instructor_identity_values(instructors.instructors[1])
    visible = filter_courses_for_instructor(courses, identity)
    assert len(visible) == 1
