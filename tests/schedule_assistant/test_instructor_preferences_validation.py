import datetime as dtm

from src.schedule_assistant.modules.schedule_config.schemas import (
    InstructorConfig,
    InstructorSlotPreferenceEntry,
    InstructorSlotPreferenceLevel,
    TermConfig,
)
from src.schedule_assistant.modules.schedule_config.validation import validate_instructors
from src.schedule_assistant.modules.solver.instructor_preferences import (
    count_discouraged_placement_violations,
    list_banned_placement_violations,
    resolve_preference_grids,
    validate_instructor_slot_preferences,
)
from src.schedule_assistant.weekday import Weekday


def _minimal_term() -> TermConfig:
    return TermConfig(
        name="Spring 2026",
        semester=TermConfig.DateRange(
            start_date=dtm.date(2026, 6, 1),
            end_date=dtm.date(2026, 8, 2),
        ),
    )


def test_validate_instructor_slot_preferences_rejects_unknown_slot() -> None:
    term = _minimal_term()
    instructor = InstructorConfig.Instructor(
        id="alice@innopolis.ru",
        slot_preferences=[
            InstructorSlotPreferenceEntry(
                weekday=Weekday.MONDAY,
                start_time=dtm.time(8, 0),
                level=InstructorSlotPreferenceLevel.BANNED,
            )
        ],
    )
    errors = validate_instructor_slot_preferences(instructor, term)
    assert any("does not match any term.time_slots" in error for error in errors)


def test_validate_instructors_rejects_duplicate_cells() -> None:
    term = _minimal_term()
    entry = InstructorSlotPreferenceEntry(
        weekday=Weekday.MONDAY,
        start_time=dtm.time(9, 0),
        level=InstructorSlotPreferenceLevel.DISCOURAGED,
    )
    config = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(
                id="alice@innopolis.ru",
                slot_preferences=[entry, entry],
            )
        ]
    )
    errors = validate_instructors(config, term=term)
    assert any("duplicate weekday+start_time" in error for error in errors)


def test_resolve_preference_grids_splits_banned_and_discouraged() -> None:
    term = _minimal_term()
    instructor = InstructorConfig.Instructor(
        id="alice@innopolis.ru",
        position="Full Professor",
        slot_preferences=[
            InstructorSlotPreferenceEntry(
                weekday=Weekday.MONDAY,
                start_time=dtm.time(9, 0),
                level=InstructorSlotPreferenceLevel.BANNED,
            ),
            InstructorSlotPreferenceEntry(
                weekday=Weekday.TUESDAY,
                start_time=dtm.time(9, 0),
                level=InstructorSlotPreferenceLevel.DISCOURAGED,
            ),
        ],
    )
    banned, discouraged = resolve_preference_grids([instructor], term)
    assert (0, 0) in banned["alice@innopolis.ru"]
    assert discouraged["alice@innopolis.ru"][(1, 0)] == 2


def test_list_banned_and_discouraged_violations() -> None:
    term = _minimal_term()
    instructor = InstructorConfig.Instructor(
        id="alice@innopolis.ru",
        slot_preferences=[
            InstructorSlotPreferenceEntry(
                weekday=Weekday.MONDAY,
                start_time=dtm.time(9, 0),
                level=InstructorSlotPreferenceLevel.BANNED,
            ),
            InstructorSlotPreferenceEntry(
                weekday=Weekday.TUESDAY,
                start_time=dtm.time(9, 0),
                level=InstructorSlotPreferenceLevel.DISCOURAGED,
            ),
        ],
    )
    banned = list_banned_placement_violations(
        instructors=[instructor],
        term=term,
        meetings=[("MONDAY", ("alice@innopolis.ru",), dtm.time(9, 0))],
    )
    assert len(banned) == 1
    weighted, count, instructors_hit = count_discouraged_placement_violations(
        instructors=[instructor],
        term=term,
        meetings=[("TUESDAY", ("alice@innopolis.ru",), dtm.time(9, 0))],
    )
    assert weighted == 1
    assert count == 1
    assert instructors_hit == {"alice@innopolis.ru"}
