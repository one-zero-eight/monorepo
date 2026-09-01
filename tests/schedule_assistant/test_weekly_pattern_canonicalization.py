import datetime as dtm

from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    TermConfig,
    WeeklyPatternSlot,
    WeeklyPatternSlotEdit,
)
from src.schedule_assistant.modules.schedule_config.weekly_pattern_canonicalization import (
    canonicalize_courses,
    canonicalize_weekly_slot,
)
from src.schedule_assistant.weekday import Weekday


def _term() -> TermConfig:
    return TermConfig(
        name="Fall 2026",
        semester=TermConfig.DateRange(
            start_date=dtm.date(2026, 9, 1),
            end_date=dtm.date(2026, 9, 30),
        ),
    )


def test_promotes_dense_uniform_edits_to_weekly_base() -> None:
    slot = WeeklyPatternSlot(
        weekday=Weekday.MONDAY,
        start_time=dtm.time(9),
        end_time=dtm.time(10, 30),
        room="107",
        instructor="old",
        edits=[
            WeeklyPatternSlotEdit(
                select_week=day,
                room="108",
                instructor="new",
            )
            for day in (
                dtm.date(2026, 9, 7),
                dtm.date(2026, 9, 14),
                dtm.date(2026, 9, 21),
                dtm.date(2026, 9, 28),
            )
        ],
    )

    normalized = canonicalize_weekly_slot(slot, _term(), [])

    assert normalized.room == "108"
    assert normalized.instructor == "new"
    assert normalized.edits is None


def test_preserves_cancellation_and_irregular_move_as_sparse_edits() -> None:
    slot = WeeklyPatternSlot(
        weekday=Weekday.MONDAY,
        start_time=dtm.time(9),
        end_time=dtm.time(10, 30),
        room="107",
        edits=[
            WeeklyPatternSlotEdit(select_week=dtm.date(2026, 9, 7), room="108"),
            WeeklyPatternSlotEdit(select_week=dtm.date(2026, 9, 14), room="108"),
            WeeklyPatternSlotEdit(select_week=dtm.date(2026, 9, 21), cancel=True),
            WeeklyPatternSlotEdit(
                select_week=dtm.date(2026, 9, 28),
                date=dtm.date(2026, 9, 29),
                start_time=dtm.time(10, 40),
                end_time=dtm.time(12, 10),
                room="108",
            ),
        ],
    )

    normalized = canonicalize_weekly_slot(slot, _term(), [])

    assert normalized.room == "108"
    assert normalized.edits == [
        WeeklyPatternSlotEdit(select_week=dtm.date(2026, 9, 21), cancel=True),
        WeeklyPatternSlotEdit(
            select_week=dtm.date(2026, 9, 28),
            date=dtm.date(2026, 9, 29),
            start_time=dtm.time(10, 40),
            end_time=dtm.time(12, 10),
        ),
    ]


def test_tie_keeps_current_base() -> None:
    slot = WeeklyPatternSlot(
        weekday=Weekday.MONDAY,
        start_time=dtm.time(9),
        end_time=dtm.time(10, 30),
        room="107",
        edits=[
            WeeklyPatternSlotEdit(select_week=dtm.date(2026, 9, 21), room="108"),
            WeeklyPatternSlotEdit(select_week=dtm.date(2026, 9, 28), room="108"),
        ],
    )

    assert canonicalize_weekly_slot(slot, _term(), []) == slot


def test_promotes_consistent_date_moves_to_new_weekday() -> None:
    slot = WeeklyPatternSlot(
        weekday=Weekday.MONDAY,
        start_time=dtm.time(9),
        end_time=dtm.time(10, 30),
        room="107",
        edits=[
            WeeklyPatternSlotEdit(
                select_week=monday,
                date=monday + dtm.timedelta(days=1),
            )
            for monday in (
                dtm.date(2026, 9, 7),
                dtm.date(2026, 9, 14),
                dtm.date(2026, 9, 21),
                dtm.date(2026, 9, 28),
            )
        ],
    )

    normalized = canonicalize_weekly_slot(slot, _term(), [])

    assert normalized.weekday == Weekday.TUESDAY
    assert normalized.edits == [
        WeeklyPatternSlotEdit(
            select_week=dtm.date(2026, 9, 1),
            cancel=True,
        )
    ]


def test_course_normalization_is_idempotent() -> None:
    course = CourseConfig(
        name="Algorithms",
        section_code="core",
        components=[
            CourseConfig.Component(
                tag="lec",
                audience=[],
                sessions=[
                    ComponentSessionSeries(
                        weekly_pattern=[
                            WeeklyPatternSlot(
                                weekday=Weekday.MONDAY,
                                start_time=dtm.time(9),
                                end_time=dtm.time(10, 30),
                                room="107",
                                edits=[
                                    WeeklyPatternSlotEdit(
                                        select_week=day,
                                        room="108",
                                    )
                                    for day in (
                                        dtm.date(2026, 9, 7),
                                        dtm.date(2026, 9, 14),
                                        dtm.date(2026, 9, 21),
                                        dtm.date(2026, 9, 28),
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
    )

    first, first_stats = canonicalize_courses([course], _term())
    second, second_stats = canonicalize_courses(first, _term())

    assert first_stats.slots_changed == 1
    assert first_stats.edits_before == 4
    assert first_stats.edits_after == 0
    assert second == first
    assert second_stats.slots_changed == 0
