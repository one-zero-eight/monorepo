import datetime as dtm

from src.schedule_assistant.modules.schedule_config.schemas import (
    CourseConfig,
    CoursesConfig,
    InstructorConfig,
    RoomConfig,
    SectionsConfig,
    TermConfig,
)
from src.schedule_assistant.modules.schedule_config.validation import (
    ValidationContext,
    validate_courses,
    validate_instructors,
)


def _term(
    *,
    positions: list[str] | None = None,
    roles: list[str] | None = None,
    tags: list[str] | None = None,
) -> TermConfig:
    return TermConfig(
        name="Test",
        semester=TermConfig.DateRange(
            start_date=dtm.date(2026, 9, 1),
            end_date=dtm.date(2026, 12, 31),
        ),
        instructor_positions=positions or [],
        course_instructor_roles=roles or [],
        course_component_tags=tags or [],
    )


def test_validate_instructors_rejects_unknown_position() -> None:
    term = _term(positions=["Full Professor", "Teaching Assistant"])
    instructors = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(id="a", position="Tutor"),
        ]
    )
    errors = validate_instructors(instructors, term=term)
    assert any("position 'Tutor' is not in term.instructor_positions" in error for error in errors)


def test_validate_instructors_allows_listed_position() -> None:
    term = _term(positions=["Full Professor", "Teaching Assistant"])
    instructors = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(id="a", position="Full Professor"),
        ]
    )
    assert validate_instructors(instructors, term=term) == []


def test_validate_instructors_skips_position_check_when_enum_empty() -> None:
    term = _term(positions=[])
    instructors = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(id="a", position="Anything"),
        ]
    )
    assert validate_instructors(instructors, term=term) == []


def test_validate_course_instructors_rejects_unknown_role() -> None:
    term = _term(roles=["Primary Instructor", "Secondary Instructor"])
    instructors = InstructorConfig(instructors=[InstructorConfig.Instructor(id="a")])
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Math",
                instructors=[CourseConfig.CourseInstructor(id="a", role="Teaching Assistant")],
                components=[],
            )
        ]
    )
    ctx = ValidationContext(
        sections=SectionsConfig(),
        rooms=RoomConfig(),
        instructors=instructors,
        courses=courses,
        term=term,
    )
    errors = validate_courses(courses, ctx)
    assert any("role 'Teaching Assistant' is not in term.course_instructor_roles" in error for error in errors)


def test_validate_course_instructors_allows_listed_role() -> None:
    term = _term(roles=["Primary Instructor", "Secondary Instructor"])
    instructors = InstructorConfig(instructors=[InstructorConfig.Instructor(id="a")])
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Math",
                instructors=[CourseConfig.CourseInstructor(id="a", role="Primary Instructor")],
                components=[],
            )
        ]
    )
    ctx = ValidationContext(
        sections=SectionsConfig(),
        rooms=RoomConfig(),
        instructors=instructors,
        courses=courses,
        term=term,
    )
    assert validate_courses(courses, ctx) == []


def test_validate_course_components_rejects_unknown_tag() -> None:
    term = _term(tags=["lec", "tut", "lab"])
    instructors = InstructorConfig(instructors=[InstructorConfig.Instructor(id="a")])
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Math",
                components=[
                    CourseConfig.Component(tag="seminar", student_groups=[], sessions=[]),
                ],
            )
        ]
    )
    ctx = ValidationContext(
        sections=SectionsConfig(),
        rooms=RoomConfig(),
        instructors=instructors,
        courses=courses,
        term=term,
    )
    errors = validate_courses(courses, ctx)
    assert any("tag 'seminar' is not in term.course_component_tags" in error for error in errors)


def test_validate_course_components_allows_listed_tag() -> None:
    term = _term(tags=["lec", "tut", "lab", "class"])
    instructors = InstructorConfig(instructors=[InstructorConfig.Instructor(id="a")])
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Math",
                components=[
                    CourseConfig.Component(tag="lec", student_groups=[], sessions=[]),
                ],
            )
        ]
    )
    ctx = ValidationContext(
        sections=SectionsConfig(),
        rooms=RoomConfig(),
        instructors=instructors,
        courses=courses,
        term=term,
    )
    assert validate_courses(courses, ctx) == []


def test_validate_course_components_skips_tag_check_when_enum_empty() -> None:
    term = _term(tags=[])
    instructors = InstructorConfig(instructors=[InstructorConfig.Instructor(id="a")])
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Math",
                components=[
                    CourseConfig.Component(tag="anything", student_groups=[], sessions=[]),
                ],
            )
        ]
    )
    ctx = ValidationContext(
        sections=SectionsConfig(),
        rooms=RoomConfig(),
        instructors=instructors,
        courses=courses,
        term=term,
    )
    assert validate_courses(courses, ctx) == []
