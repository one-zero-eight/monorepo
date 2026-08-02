import datetime as dtm

from src.schedule_assistant.modules.schedule_config.schemas import (
    InstructorConfig,
    TermConfig,
)
from src.schedule_assistant.modules.schedule_config.validation import validate_instructors


def _term(*, roles: list[str]) -> TermConfig:
    return TermConfig(
        name="Test",
        semester=TermConfig.DateRange(
            start_date=dtm.date(2026, 9, 1),
            end_date=dtm.date(2026, 12, 31),
        ),
        instructor_roles=roles,
    )


def test_validate_instructors_rejects_unknown_role() -> None:
    term = _term(roles=["Professor", "TA"])
    instructors = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(id="a", position="Tutor"),
        ]
    )
    errors = validate_instructors(instructors, term=term)
    assert any("position 'Tutor' is not in term.instructor_roles" in error for error in errors)


def test_validate_instructors_allows_listed_role() -> None:
    term = _term(roles=["Professor", "TA"])
    instructors = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(id="a", position="Professor"),
        ]
    )
    assert validate_instructors(instructors, term=term) == []


def test_validate_instructors_skips_role_check_when_enum_empty() -> None:
    term = _term(roles=[])
    instructors = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(id="a", position="Anything"),
        ]
    )
    assert validate_instructors(instructors, term=term) == []
