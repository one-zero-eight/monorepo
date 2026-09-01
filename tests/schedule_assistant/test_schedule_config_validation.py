import datetime as dtm

import pytest
from httpx import AsyncClient

from src.schedule_assistant.modules.schedule_config.repository import ScheduleConfigRepository
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    CoursesConfig,
    InstructorConfig,
    RoomConfig,
    SectionConfig,
    SectionsConfig,
    SessionOccurrence,
    StudentsGroups,
    TermConfig,
    WeeklyPatternSlot,
)
from src.schedule_assistant.modules.schedule_config.validation import (
    ValidationContext,
    validate_courses,
    validate_instructors,
    validate_resource_update,
    validate_rooms_update,
    validate_sections,
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


def test_validate_sections_rejects_duplicate_group_codes() -> None:
    config = SectionsConfig(
        sections=[SectionConfig(code="core", name="Core", programs=[])],
        students_groups=[
            StudentsGroups(code="G1", kind="core"),
            StudentsGroups(code="g1", kind="core"),
        ],
    )
    errors = validate_sections(config)
    assert any("Duplicate students_groups code" in error for error in errors)


def test_validate_courses_rejects_duplicate_names() -> None:
    ctx = ValidationContext(
        sections=SectionsConfig(sections=[SectionConfig(code="core", name="Core", programs=[])]),
        rooms=RoomConfig(),
        instructors=InstructorConfig(),
        courses=CoursesConfig(),
    )
    courses = CoursesConfig(
        courses=[
            CourseConfig(name="Algorithms", section_code="core", components=[]),
            CourseConfig(name="algorithms", section_code="core", components=[]),
        ],
    )
    errors = validate_courses(courses, ctx)
    assert any("Duplicate course name" in error for error in errors)


def test_validate_courses_rejects_unknown_student_group() -> None:
    ctx = ValidationContext(
        sections=SectionsConfig(
            sections=[
                SectionConfig(
                    code="core",
                    name="Core",
                    programs=[SectionConfig.SectionProgram(code="BS", name="BS", groups=["SUM26-AAI"])],
                )
            ],
            students_groups=[StudentsGroups(code="SUM26-AAI", kind="elective")],
        ),
        rooms=RoomConfig(),
        instructors=InstructorConfig(
            instructors=[InstructorConfig.Instructor(id="teacher@innopolis.ru")],
        ),
        courses=CoursesConfig(),
    )
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Elective",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="class",
                        audience=["UNKNOWN-GROUP"],
                    ),
                ],
            ),
        ],
    )
    errors = validate_courses(courses, ctx)
    assert any("unknown group or selector" in error for error in errors)


def test_validate_courses_accepts_online_room() -> None:
    ctx = ValidationContext(
        sections=SectionsConfig(
            sections=[
                SectionConfig(
                    code="core",
                    name="Core",
                    programs=[SectionConfig.SectionProgram(code="BS", name="BS", groups=["SUM26-AAI"])],
                )
            ],
            students_groups=[StudentsGroups(code="SUM26-AAI", kind="elective")],
        ),
        rooms=RoomConfig(),
        instructors=InstructorConfig(
            instructors=[InstructorConfig.Instructor(id="teacher@innopolis.ru")],
        ),
        courses=CoursesConfig(),
    )
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Online elective",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="class",
                        audience=["SUM26-AAI"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["SUM26-AAI"],
                                dates_pattern=[
                                    SessionOccurrence(
                                        date=dtm.date(2026, 6, 8),
                                        start_time=dtm.time(14, 20),
                                        end_time=dtm.time(15, 50),
                                        room="ONLINE",
                                        instructor="teacher@innopolis.ru",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            CourseConfig(
                name="Online core",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        audience=["SUM26-AAI"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["SUM26-AAI"],
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.MONDAY,
                                        start_time=dtm.time(10, 0),
                                        end_time=dtm.time(11, 30),
                                        room="ONLINE",
                                        instructor="teacher@innopolis.ru",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    errors = validate_courses(courses, ctx)
    assert errors == []


def test_validate_rooms_update_ignores_online_references() -> None:
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Online elective",
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
                                        room="ONLINE",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    errors = validate_rooms_update(RoomConfig(), RoomConfig(), courses=courses)
    assert errors == []


@pytest.mark.parametrize("invalid_room", ["Online", "Онлайн", "ОНЛАЙН", "online"])
def test_validate_courses_rejects_non_canonical_online_rooms(invalid_room: str) -> None:
    ctx = ValidationContext(
        sections=SectionsConfig(sections=[SectionConfig(code="core", name="Core", programs=[])]),
        rooms=RoomConfig(),
        instructors=InstructorConfig(),
        courses=CoursesConfig(),
    )
    courses = CoursesConfig(
        courses=[
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
                                        room=invalid_room,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    errors = validate_courses(courses, ctx)
    assert any("unknown room" in error for error in errors)


def test_validate_courses_rejects_unknown_instructor() -> None:
    ctx = ValidationContext(
        sections=SectionsConfig(
            sections=[
                SectionConfig(
                    code="core",
                    name="Core",
                    programs=[SectionConfig.SectionProgram(code="BS", name="BS", groups=["SUM26-AAI"])],
                )
            ],
            students_groups=[StudentsGroups(code="SUM26-AAI", kind="elective")],
        ),
        rooms=RoomConfig(rooms=[RoomConfig.Room(id="108", name="Room 108", capacity=100)]),
        instructors=InstructorConfig(),
        courses=CoursesConfig(),
    )
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Elective",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="class",
                        audience=["SUM26-AAI"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["SUM26-AAI"],
                                dates_pattern=[
                                    SessionOccurrence(
                                        date=dtm.date(2026, 6, 8),
                                        start_time=dtm.time(14, 20),
                                        end_time=dtm.time(15, 50),
                                        instructor="teacher@innopolis.ru",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    errors = validate_courses(courses, ctx)
    assert any("unknown instructor" in error for error in errors)


def test_validate_courses_allows_missing_room_and_instructor() -> None:
    ctx = ValidationContext(
        sections=SectionsConfig(
            sections=[
                SectionConfig(
                    code="core",
                    name="Core",
                    programs=[SectionConfig.SectionProgram(code="BS", name="BS", groups=["G1"])],
                )
            ],
            students_groups=[StudentsGroups(code="G1", kind="core")],
        ),
        rooms=RoomConfig(rooms=[RoomConfig.Room(id="108", name="Room 108", capacity=100)]),
        instructors=InstructorConfig(instructors=[InstructorConfig.Instructor(id="t@innopolis.ru")]),
        courses=CoursesConfig(),
    )
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Draft",
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
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    assert validate_courses(courses, ctx) == []


def test_validate_instructors_rejects_duplicate_ids() -> None:
    config = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(id="teacher@innopolis.ru"),
            InstructorConfig.Instructor(id="Teacher@innopolis.ru"),
        ],
    )
    errors = validate_instructors(config)
    assert any("Duplicate instructor id" in error for error in errors)


def test_validate_instructors_rejects_duplicate_emails() -> None:
    config = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(
                id="teacher-one",
                email=" Teacher@Innopolis.RU ",
            ),
            InstructorConfig.Instructor(
                id="teacher-two",
                email="teacher@innopolis.ru",
            ),
        ],
    )
    errors = validate_instructors(config)
    assert any("Duplicate instructor email" in error for error in errors)


def test_validate_resource_update_blocks_removing_referenced_instructor() -> None:
    old = InstructorConfig(
        instructors=[InstructorConfig.Instructor(id="teacher@innopolis.ru")],
    )
    new = InstructorConfig()
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Elective",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="class",
                        instructor_pool=["teacher@innopolis.ru"],
                    ),
                ],
            ),
        ],
    )
    ctx = ValidationContext(
        sections=SectionsConfig(sections=[SectionConfig(code="core", name="Core", programs=[])]),
        rooms=RoomConfig(),
        instructors=new,
        courses=courses,
    )
    errors = validate_resource_update("instructors", new, old, ctx)
    assert any("still referenced in courses" in error for error in errors)


@pytest.mark.asyncio
async def test_put_courses_returns_422_for_invalid_references(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term(), saved_by="test@test.com")
    schedule_config_repo.set_sections(
        SectionsConfig(
            sections=[
                SectionConfig(
                    code="core",
                    name="Core",
                    programs=[SectionConfig.SectionProgram(code="BS", name="BS", groups=["SUM26-AAI"])],
                )
            ],
            students_groups=[StudentsGroups(code="SUM26-AAI", kind="elective")],
        ),
        saved_by="test@test.com",
    )

    response = await authenticated_client.post(
        "/schedule-config/courses",
        json=CourseConfig(
            name="Elective",
            section_code="core",
            components=[
                CourseConfig.Component(
                    tag="class",
                    audience=["UNKNOWN-GROUP"],
                ),
            ],
        ).model_dump(mode="json"),
    )
    assert response.status_code == 422
    assert "unknown group or selector" in response.json()["detail"]["errors"][0]


def test_validate_courses_rejects_unknown_section_code() -> None:
    ctx = ValidationContext(
        sections=SectionsConfig(sections=[SectionConfig(code="core", name="Core", programs=[])]),
        rooms=RoomConfig(),
        instructors=InstructorConfig(),
        courses=CoursesConfig(),
    )
    courses = CoursesConfig(
        courses=[
            CourseConfig(name="Algorithms", section_code="missing", components=[]),
        ],
    )
    errors = validate_courses(courses, ctx)
    assert any("unknown section" in error for error in errors)


def test_validate_courses_rejects_audience_outside_section() -> None:
    ctx = ValidationContext(
        sections=SectionsConfig(
            sections=[
                SectionConfig(
                    code="core",
                    name="Core",
                    programs=[
                        SectionConfig.SectionProgram(code="BS", name="BS", groups=["CORE-01"]),
                    ],
                ),
                SectionConfig(
                    code="electives",
                    name="Electives",
                    programs=[
                        SectionConfig.SectionProgram(code="ELEC", name="Electives", groups=["ELEC-01"]),
                    ],
                ),
            ],
            students_groups=[
                StudentsGroups(code="CORE-01", kind="core"),
                StudentsGroups(code="ELEC-01", kind="elective"),
            ],
        ),
        rooms=RoomConfig(),
        instructors=InstructorConfig(),
        courses=CoursesConfig(),
    )
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Algorithms",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        audience=["ELEC-01"],
                    ),
                ],
            ),
        ],
    )
    errors = validate_courses(courses, ctx)
    assert any("outside section" in error for error in errors)
