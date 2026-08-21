import datetime as dtm

from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    InstructorConfig,
    SessionOccurrence,
    WeeklyPatternSlot,
)
from src.schedule_assistant.modules.schedule_config.visibility import (
    filter_courses_for_instructor,
    filter_scheduled_instructors,
    instructor_identity_values,
)
from src.schedule_assistant.weekday import Weekday


def test_filter_matches_instructor_by_display_name() -> None:
    instructors = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(id="a.shamraev@innopolis.ru", name_en="Aleksei Shamraev"),
            InstructorConfig.Instructor(id="other@innopolis.ru", name_en="Other Person"),
        ],
    )
    courses = [
        CourseConfig(
            name="Elective",
            section_code="core",
            components=[
                CourseConfig.Component(
                    tag="class",
                    sessions=[
                        ComponentSessionSeries(
                            dates_pattern=[
                                SessionOccurrence(
                                    date=dtm.date(2026, 6, 8),
                                    start_time=dtm.time(14, 20),
                                    end_time=dtm.time(15, 50),
                                    instructor="Aleksei Shamraev",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ]

    filtered = filter_scheduled_instructors(instructors, courses)
    assert [instructor.id for instructor in filtered.instructors] == ["a.shamraev@innopolis.ru"]


def test_filter_includes_weekly_pattern_instructors() -> None:
    instructors = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(id="teacher@innopolis.ru"),
            InstructorConfig.Instructor(id="unused@innopolis.ru"),
        ],
    )
    courses = [
        CourseConfig(
            name="Core",
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
                                    instructor="teacher@innopolis.ru",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ]

    filtered = filter_scheduled_instructors(instructors, courses)
    assert [instructor.id for instructor in filtered.instructors] == ["teacher@innopolis.ru"]


def test_filter_courses_keeps_only_matching_occurrences() -> None:
    instructors = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(id="teacher@innopolis.ru"),
            InstructorConfig.Instructor(id="other@innopolis.ru"),
        ],
    )
    courses = [
        CourseConfig(
            name="Elective",
            section_code="core",
            components=[
                CourseConfig.Component(
                    tag="class",
                    sessions=[
                        ComponentSessionSeries(
                            dates_pattern=[
                                SessionOccurrence(
                                    date=dtm.date(2026, 6, 8),
                                    start_time=dtm.time(14, 20),
                                    end_time=dtm.time(15, 50),
                                    instructor="teacher@innopolis.ru",
                                ),
                                SessionOccurrence(
                                    date=dtm.date(2026, 6, 15),
                                    start_time=dtm.time(14, 20),
                                    end_time=dtm.time(15, 50),
                                    instructor="other@innopolis.ru",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ]

    filtered = filter_courses_for_instructor(courses, instructor_identity_values(instructors.instructors[0]))
    assert filtered
    assert filtered[0].components
    assert filtered[0].components[0].sessions
    dates_pattern = filtered[0].components[0].sessions[0].dates_pattern
    assert dates_pattern is not None
    assert len(dates_pattern) == 1
    assert dates_pattern[0].instructor == "teacher@innopolis.ru"
