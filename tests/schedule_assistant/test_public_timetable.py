import datetime as dtm

import pytest
from httpx import AsyncClient

from src.schedule_assistant.modules.public_timetable.schemas import PublicTimetable
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    InstructorConfig,
    InstructorSlotPreferenceEntry,
    InstructorSlotPreferenceLevel,
    RoomConfig,
    ScheduleConfig,
    ScheduleConfigUpdate,
    SectionConfig,
    SessionOccurrence,
    StudentsGroups,
    TermConfig,
    TermPartialUpdate,
    WeeklyAlternation,
    WeeklyPatternSlot,
    WeeklyPatternSlotEdit,
)
from src.schedule_assistant.weekday import Weekday


def timetable_config() -> ScheduleConfig:
    return ScheduleConfig(
        term=TermConfig(
            name="Fall 2026",
            semester=TermConfig.DateRange(start_date=dtm.date(2026, 9, 1), end_date=dtm.date(2026, 9, 30)),
            sections=[
                SectionConfig(
                    code="core",
                    name="Core courses",
                    default_layout="groups",
                    programs=[
                        SectionConfig.SectionProgram(
                            code="BS",
                            name="Bachelors",
                            tracks=[SectionConfig.SectionProgram.ProgramTrack(code="CS", name="CS", groups=["G1"])],
                            groups=["G2", "G3"],
                            semester=TermConfig.DateRange(
                                start_date=dtm.date(2026, 9, 1), end_date=dtm.date(2026, 9, 30)
                            ),
                        )
                    ],
                )
            ],
            instructor_positions=["Professor"],
            course_instructor_roles=["Lecturer"],
            course_component_tags=["lec"],
        ),
        rooms=[RoomConfig.Room(id="108", name="Room 108", capacity=30, features={"private": "not public"})],
        instructors=[
            InstructorConfig.Instructor(
                id="teacher@innopolis.ru",
                email="teacher@innopolis.ru",
                name_en="Teacher",
                name_ru="Преподаватель",
                alias="teacher",
                position="Professor",
                slot_preferences=[
                    InstructorSlotPreferenceEntry(
                        weekday=Weekday.MONDAY,
                        start_time=dtm.time(9),
                        level=InstructorSlotPreferenceLevel.BANNED,
                    )
                ],
            )
        ],
        students_groups=[
            StudentsGroups(
                code="G1", name="Group one", estimated_size=20, students=[" TEST@TEST.COM ", "private@innopolis.ru"]
            ),
            StudentsGroups(code="G2", name="Group two", students=["test@test.com"]),
            StudentsGroups(code="G3", students=["other@innopolis.ru"]),
        ],
        courses=[
            CourseConfig(
                name="Algorithms",
                short_name="Algo",
                name_ru="Алгоритмы",
                short_name_ru="Алго",
                color="#AABBCC",
                section_code="core",
                instructors=[CourseConfig.CourseInstructor(id="teacher@innopolis.ru", role="Lecturer")],
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        audience=["@BS/CS"],
                        instructor_pool=["teacher@innopolis.ru"],
                        per_week=1,
                        expected_enrollment=20,
                        per_group=True,
                        sessions=[
                            ComponentSessionSeries(
                                audience=["G1"],
                                notes="Bring a laptop",
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.MONDAY,
                                        start_time=dtm.time(9),
                                        end_time=dtm.time(10, 30),
                                        room="108",
                                        instructor="teacher@innopolis.ru",
                                        alternation=WeeklyAlternation(anchor_week=dtm.date(2026, 9, 7)),
                                        edits=[
                                            WeeklyPatternSlotEdit(select_week=dtm.date(2026, 9, 7), notes=""),
                                            WeeklyPatternSlotEdit(
                                                select_week=dtm.date(2026, 9, 21), notes="Read chapter 2"
                                            ),
                                        ],
                                    )
                                ],
                                dates_pattern=[
                                    SessionOccurrence(
                                        date=dtm.date(2026, 9, 8),
                                        start_time=dtm.time(9),
                                        end_time=dtm.time(10, 30),
                                        notes=None,
                                    ),
                                    SessionOccurrence(
                                        date=dtm.date(2026, 9, 15),
                                        start_time=dtm.time(9),
                                        end_time=dtm.time(10, 30),
                                        notes="",
                                    ),
                                    SessionOccurrence(
                                        date=dtm.date(2026, 9, 22),
                                        start_time=dtm.time(9),
                                        end_time=dtm.time(10, 30),
                                        notes="Read chapter 3",
                                    ),
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
    )


def seed_timetable(repo) -> ScheduleConfig:
    config = timetable_config()
    stored, _revision = repo.set_config(
        ScheduleConfigUpdate(
            term=TermPartialUpdate.model_validate(config.term.model_dump()),
            rooms=config.rooms,
            instructors=config.instructors,
            students_groups=config.students_groups,
            courses=config.courses,
        )
    )
    return stored


def assert_no_private_fields(value: object) -> None:
    forbidden = {
        "students",
        "slot_preferences",
        "instructor_pool",
        "expected_enrollment",
        "estimated_size",
        "per_week",
        "per_semester",
        "per_group",
        "relates_to",
        "features",
        "room_attributes",
        "instructor_positions",
        "course_instructor_roles",
        "course_component_tags",
    }
    if isinstance(value, dict):
        assert not forbidden.intersection(value)
        for child in value.values():
            assert_no_private_fields(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_private_fields(child)


@pytest.mark.asyncio
async def test_timetable_is_anonymous_and_sanitized(fastapi_test_client: AsyncClient, schedule_data_repo) -> None:
    stored = seed_timetable(schedule_data_repo)
    response = await fastapi_test_client.get("/timetable")
    assert response.status_code == 200
    data = response.json()
    assert_no_private_fields(data)
    assert "private@innopolis.ru" not in response.text
    assert "TEST@TEST.COM" not in response.text
    assert data["term"]["sections"][0]["programs"][0]["tracks"][0]["groups"] == ["G1"]
    assert data["term"]["sections"][0]["default_layout"] == "groups"
    assert data["rooms"] == [{"id": "108", "name": "Room 108", "capacity": 30}]
    assert data["instructors"][0] == {
        "id": "teacher@innopolis.ru",
        "email": "teacher@innopolis.ru",
        "name_en": "Teacher",
        "name_ru": "Преподаватель",
        "alias": "teacher",
        "position": "Professor",
    }
    course = data["courses"][0]
    assert course["color"] == "#AABBCC"
    assert course["instructors"] == [{"id": "teacher@innopolis.ru", "role": "Lecturer"}]
    session = course["components"][0]["sessions"][0]
    assert session["notes"] == "Bring a laptop"
    assert [item["notes"] for item in session["dates_pattern"]] == [None, "", "Read chapter 3"]
    assert [item["notes"] for item in session["weekly_pattern"][0]["edits"]] == ["", "Read chapter 2"]
    assert PublicTimetable.model_validate(data).model_dump() == PublicTimetable.model_validate(stored).model_dump()
    assert schedule_data_repo.get_assembled().students_groups[0].students
    assert schedule_data_repo.get_assembled().instructors[0].slot_preferences


@pytest.mark.asyncio
async def test_timetable_without_term_returns_not_found(fastapi_test_client: AsyncClient, schedule_data_repo) -> None:
    response = await fastapi_test_client.get("/timetable")
    assert response.status_code == 404


def test_student_groups_require_valid_authentication(schedule_assistant_client) -> None:
    assert schedule_assistant_client.get("/me/student-groups").status_code == 401
    assert (
        schedule_assistant_client.get("/me/student-groups", headers={"Authorization": "Bearer invalid"}).status_code
        == 401
    )


@pytest.mark.asyncio
async def test_student_groups_use_verified_email_not_query(
    authenticated_client: AsyncClient, schedule_data_repo
) -> None:
    seed_timetable(schedule_data_repo)
    response = await authenticated_client.get("/me/student-groups", params={"email": "other@innopolis.ru"})
    assert response.status_code == 200
    assert response.json() == ["G1", "G2"]


@pytest.mark.asyncio
async def test_student_groups_without_membership_are_empty(
    authenticated_client: AsyncClient, schedule_data_repo
) -> None:
    response = await authenticated_client.get("/me/student-groups")
    assert response.status_code == 200
    assert response.json() == []


def test_public_openapi_contract_has_no_editor_models(fastapi_app) -> None:
    schema = fastapi_app.openapi()
    public_route = schema["paths"]["/timetable"]["get"]
    assert not public_route.get("security")
    assert public_route["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PublicTimetable"
    }
    membership_route = schema["paths"]["/me/student-groups"]["get"]
    assert membership_route["security"]
    membership_schema = membership_route["responses"]["200"]["content"]["application/json"]["schema"]
    assert membership_schema["type"] == "array"
    assert membership_schema["items"] == {"type": "string"}
    pending = ["PublicTimetable"]
    visited = set()

    def check_node(node: object) -> None:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].rsplit("/", 1)[-1]
                assert name.startswith("Public") or name == "Weekday"
                pending.append(name)
            assert_no_private_fields(node.get("properties", {}))
            for value in node.values():
                check_node(value)
        elif isinstance(node, list):
            for item in node:
                check_node(item)

    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        check_node(schema["components"]["schemas"][name])


def test_whitelist_ignores_future_editor_fields() -> None:
    config = timetable_config()
    config.courses[0].components[0].__dict__["future_private_field"] = "must not leak"
    config.instructors[0].__dict__["future_private_contact"] = "must not leak"
    assert "must not leak" not in PublicTimetable.model_validate(config).model_dump_json()
