import datetime as dtm

from src.schedule_assistant.modules.schedule_config.instructor_meetings import (
    count_instructor_meetings_in_term,
    count_meetings_by_instructor,
)
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    SessionOccurrence,
    TermConfig,
    TermTimeSlot,
    WeeklyPatternSlot,
    WeeklyPatternSlotEdit,
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
    )


def test_occurrence_counts_once() -> None:
    courses = [
        CourseConfig(
            name="Course",
            section_code="core",
            components=[
                CourseConfig.Component(
                    tag="lec",
                    sessions=[
                        ComponentSessionSeries(
                            audience=["G1"],
                            dates_pattern=[
                                SessionOccurrence(
                                    date=dtm.date(2026, 9, 2),
                                    start_time=dtm.time(9, 0),
                                    end_time=dtm.time(10, 30),
                                    instructor="a@iu.ru",
                                ),
                                SessionOccurrence(
                                    date=dtm.date(2026, 9, 9),
                                    start_time=dtm.time(9, 0),
                                    end_time=dtm.time(10, 30),
                                    instructor="b@iu.ru",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ]
    assert count_instructor_meetings_in_term("a@iu.ru", courses, _term()) == 1
    assert count_instructor_meetings_in_term("b@iu.ru", courses, _term()) == 1
    assert count_instructor_meetings_in_term("c@iu.ru", courses, _term()) == 0


def test_weekly_pattern_expands_per_week_and_respects_cancel() -> None:
    # Mondays in 2026-09-01..2026-09-28: 7, 14, 21, 28 → 4 weeks
    courses = [
        CourseConfig(
            name="Course",
            section_code="core",
            components=[
                CourseConfig.Component(
                    tag="lab",
                    sessions=[
                        ComponentSessionSeries(
                            audience=["G1"],
                            weekly_pattern=[
                                WeeklyPatternSlot(
                                    weekday=Weekday.MONDAY,
                                    start_time=dtm.time(9, 0),
                                    end_time=dtm.time(10, 30),
                                    instructor="a@iu.ru",
                                    edits=[
                                        WeeklyPatternSlotEdit(
                                            select_week=dtm.date(2026, 9, 14),
                                            cancel=True,
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
    assert count_instructor_meetings_in_term("a@iu.ru", courses, _term()) == 3


def test_weekly_edit_can_reassign_instructor() -> None:
    courses = [
        CourseConfig(
            name="Course",
            section_code="core",
            components=[
                CourseConfig.Component(
                    tag="lab",
                    sessions=[
                        ComponentSessionSeries(
                            audience=["G1"],
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
    counts = count_meetings_by_instructor(courses, _term(), ["a@iu.ru", "b@iu.ru"])
    assert counts["a@iu.ru"] == 3
    assert counts["b@iu.ru"] == 1


def test_weekly_pattern_without_edits_counts_all_weeks() -> None:
    courses = [
        CourseConfig(
            name="Course",
            section_code="core",
            components=[
                CourseConfig.Component(
                    tag="lab",
                    sessions=[
                        ComponentSessionSeries(
                            audience=["G1"],
                            weekly_pattern=[
                                WeeklyPatternSlot(
                                    weekday=Weekday.MONDAY,
                                    start_time=dtm.time(9, 0),
                                    end_time=dtm.time(10, 30),
                                    instructor="a@iu.ru",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ]
    assert count_instructor_meetings_in_term("a@iu.ru", courses, _term()) == 4
