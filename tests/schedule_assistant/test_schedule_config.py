import datetime as dtm

import pytest
from httpx import AsyncClient

from src.schedule_assistant.db.models import TermRow
from src.schedule_assistant.modules.schedule_config.repository import ScheduleConfigRepository
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    InstructorConfig,
    RoomConfig,
    ScheduleConfig,
    SectionConfig,
    SectionsConfig,
    SessionOccurrence,
    StudentsGroups,
    TermConfig,
    WeeklyPatternSlot,
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


def _minimal_term_settings() -> TermConfig:
    return _minimal_term()


def _core_sections(*, group_codes: list[str] | None = None) -> SectionsConfig:
    students_groups = [
        StudentsGroups(
            code=code,
        )
        for code in (group_codes or [])
    ]
    return SectionsConfig(
        sections=[SectionConfig(code="core", name="Core", programs=[])],
        students_groups=students_groups,
    )


def _revision(etag_header: str) -> int:
    return int(etag_header.strip('"'))


@pytest.mark.asyncio
async def test_get_assembled_schedule_config_requires_term(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
) -> None:
    response = await authenticated_client.get("/schedule-config/")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_term_returns_null_when_missing(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
) -> None:
    response = await authenticated_client.get("/schedule-config/term")
    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.asyncio
async def test_put_term_requires_moderator(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.moderator_emails", ["moderator@innopolis.university"]
    )
    response = await authenticated_client.put(
        "/schedule-config/term",
        json=_minimal_term_settings().model_dump(mode="json"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_entity_crud_and_assembled_get(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])

    assert (
        await authenticated_client.put(
            "/schedule-config/term",
            json=_minimal_term_settings().model_dump(mode="json"),
        )
    ).status_code == 200
    schedule_config_repo.set_sections(_core_sections())
    assert (
        await authenticated_client.post(
            "/schedule-config/rooms",
            json=RoomConfig.Room(id="108", name="Lecture Room 108", capacity=312).model_dump(mode="json"),
        )
    ).status_code == 201
    assert (
        await authenticated_client.post(
            "/schedule-config/courses",
            json={"name": "Empty", "section_code": "core", "components": []},
        )
    ).status_code == 201
    assert (
        await authenticated_client.post("/schedule-config/instructors", json={"id": "teacher@innopolis.ru"})
    ).status_code == 201

    assembled_response = await authenticated_client.get("/schedule-config/")
    assert assembled_response.status_code == 200
    assembled = ScheduleConfig.model_validate(assembled_response.json())
    assert assembled.term.name == "Spring 2026"
    assert assembled.rooms == [RoomConfig.Room(id="108", name="Lecture Room 108", capacity=312)]
    assert _revision(assembled_response.headers["etag"]) == 5


@pytest.mark.asyncio
async def test_course_color_crud_updates_revision(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term_settings())
    schedule_config_repo.set_sections(_core_sections())
    baseline = schedule_config_repo.get_revision()

    create_response = await authenticated_client.post(
        "/schedule-config/courses",
        json={"name": "Algorithms", "color": "#a1b2c3", "section_code": "core", "components": []},
    )
    assert create_response.status_code == 201
    assert create_response.json()["color"] == "#A1B2C3"
    assert _revision(create_response.headers["etag"]) == baseline + 1

    update_response = await authenticated_client.put(
        "/schedule-config/courses/Algorithms",
        json={"name": "Algorithms", "color": "#445566", "section_code": "core", "components": []},
    )
    assert update_response.status_code == 200
    stored_course = schedule_config_repo.get_course("Algorithms")
    assert stored_course is not None
    assert stored_course.color == "#445566"
    assert _revision(update_response.headers["etag"]) == baseline + 2


@pytest.mark.asyncio
async def test_put_term_bumps_revision_and_persists_value(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    first_response = await authenticated_client.put(
        "/schedule-config/term",
        json=_minimal_term_settings().model_dump(mode="json"),
    )
    assert first_response.status_code == 200
    assert _revision(first_response.headers["etag"]) == 1

    second_response = await authenticated_client.put(
        "/schedule-config/term",
        json=_minimal_term_settings().model_copy(update={"name": "Summer 2026"}).model_dump(mode="json"),
    )
    assert second_response.status_code == 200
    assert _revision(second_response.headers["etag"]) == 2
    term = schedule_config_repo.get_term()
    assert term is not None
    assert term.name == "Summer 2026"
    assert schedule_config_repo.get_revision() == 2


@pytest.mark.asyncio
async def test_identical_put_does_not_bump_revision(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term_settings())
    baseline = schedule_config_repo.get_revision()
    term = _minimal_term_settings()

    first_response = await authenticated_client.put("/schedule-config/term", json=term.model_dump(mode="json"))
    assert first_response.status_code == 200
    assert _revision(first_response.headers["etag"]) == baseline

    second_response = await authenticated_client.put("/schedule-config/term", json=term.model_dump(mode="json"))
    assert second_response.status_code == 200
    assert _revision(second_response.headers["etag"]) == baseline
    assert schedule_config_repo.get_revision() == baseline


@pytest.mark.asyncio
async def test_empty_config_update_and_failed_write_keep_revision(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term_settings())
    schedule_config_repo.set_sections(_core_sections())
    baseline = schedule_config_repo.get_revision()

    empty_response = await authenticated_client.put("/schedule-config/", json={})
    assert empty_response.status_code == 200
    assert _revision(empty_response.headers["etag"]) == baseline
    assert schedule_config_repo.get_revision() == baseline

    failed_response = await authenticated_client.post(
        "/schedule-config/courses",
        json={"name": "Algorithms", "section_code": "missing", "components": []},
    )
    assert failed_response.status_code == 422
    assert schedule_config_repo.get_revision() == baseline
    assert schedule_config_repo.get_course("Algorithms") is None


@pytest.mark.asyncio
async def test_multi_resource_put_bumps_revision_once(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term_settings())
    schedule_config_repo.set_sections(_core_sections())
    baseline = schedule_config_repo.get_revision()

    response = await authenticated_client.put(
        "/schedule-config/",
        json={
            "rooms": [{"id": "108", "name": "Lecture Room 108", "capacity": 312}],
            "courses": [{"name": "Algorithms", "section_code": "core", "components": []}],
        },
    )
    assert response.status_code == 200
    assert _revision(response.headers["etag"]) == baseline + 1
    assert schedule_config_repo.get_revision() == baseline + 1
    assert len(schedule_config_repo.list_rooms()) == 1
    assert schedule_config_repo.get_course("Algorithms") is not None


@pytest.mark.asyncio
async def test_history_routes_and_schemas_are_removed(authenticated_client: AsyncClient) -> None:
    for path in (
        "/schedule-config/history",
        "/schedule-config/history/example",
        "/schedule-config/history/example/snapshot",
    ):
        response = await authenticated_client.get(path)
        assert response.status_code == 404

    openapi = (await authenticated_client.get("/openapi.json")).json()
    assert not any(path.startswith("/schedule-config/history") for path in openapi["paths"])
    schema_names = openapi.get("components", {}).get("schemas", {})
    assert "ConfigChangeEvent" not in schema_names
    assert "ConfigChangeEventSummary" not in schema_names


@pytest.mark.asyncio
async def test_update_course_leaves_other_resources_unchanged(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term_settings())
    schedule_config_repo.set_sections(_core_sections())
    schedule_config_repo.create_room(RoomConfig.Room(id="108", name="Lecture Room 108", capacity=312))
    schedule_config_repo.create_course(CourseConfig(name="Algorithms", section_code="core", components=[]))

    response = await authenticated_client.put(
        "/schedule-config/courses/Algorithms",
        json=CourseConfig(name="Algorithms", section_code="core", components=[]).model_dump(mode="json"),
    )
    assert response.status_code == 200

    assembled_response = await authenticated_client.get("/schedule-config/")
    assert assembled_response.json()["rooms"][0]["id"] == "108"


@pytest.mark.asyncio
async def test_non_moderator_sees_only_scheduled_instructors(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.moderator_emails", ["moderator@innopolis.university"]
    )
    schedule_config_repo.set_term(_minimal_term_settings())
    schedule_config_repo.set_sections(
        SectionsConfig(
            sections=[
                SectionConfig(
                    code="core",
                    name="Core",
                    programs=[SectionConfig.SectionProgram(code="BS", name="BS", groups=["SUM26-AAI"])],
                )
            ],
            students_groups=[
                StudentsGroups(
                    code="SUM26-AAI",
                )
            ],
        )
    )
    schedule_config_repo.create_instructor(
        InstructorConfig.Instructor(id="teacher@innopolis.ru", email="teacher@innopolis.ru", name_en="Teacher")
    )
    schedule_config_repo.create_instructor(
        InstructorConfig.Instructor(id="pool@innopolis.ru", email="pool@innopolis.ru", name_en="Pool Only")
    )
    schedule_config_repo.create_course(
        CourseConfig(
            name="Agentic AI",
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
        )
    )

    assembled_response = await authenticated_client.get("/schedule-config/")
    assert assembled_response.status_code == 200
    assembled_instructor_ids = [instructor["id"] for instructor in assembled_response.json()["instructors"]]
    assert assembled_instructor_ids == ["teacher@innopolis.ru"]


@pytest.mark.asyncio
async def test_delete_course(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term_settings())
    schedule_config_repo.set_sections(_core_sections())
    schedule_config_repo.create_course(CourseConfig(name="Algorithms", section_code="core", components=[]))

    response = await authenticated_client.delete("/schedule-config/courses/Algorithms")
    assert response.status_code == 204
    assert schedule_config_repo.get_course("Algorithms") is None


@pytest.mark.asyncio
async def test_moderator_sees_all_instructors(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term_settings())
    schedule_config_repo.set_sections(
        SectionsConfig(
            sections=[
                SectionConfig(
                    code="core",
                    name="Core",
                    programs=[SectionConfig.SectionProgram(code="BS", name="BS", groups=["SUM26-AAI"])],
                )
            ],
            students_groups=[
                StudentsGroups(
                    code="SUM26-AAI",
                )
            ],
        )
    )
    schedule_config_repo.create_instructor(
        InstructorConfig.Instructor(id="teacher@innopolis.ru", email="teacher@innopolis.ru")
    )
    schedule_config_repo.create_instructor(
        InstructorConfig.Instructor(id="pool@innopolis.ru", email="pool@innopolis.ru")
    )
    schedule_config_repo.create_course(
        CourseConfig(
            name="Agentic AI",
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
        )
    )

    assembled_response = await authenticated_client.get("/schedule-config/")
    assert assembled_response.status_code == 200
    assert len(assembled_response.json()["instructors"]) == 2


def _yaml_headers() -> dict[str, str]:
    return {"Content-Type": "text/yaml"}


@pytest.mark.asyncio
async def test_put_full_schedule_config_json(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    config = ScheduleConfig(
        term=_minimal_term_settings(),
        rooms=[RoomConfig.Room(id="108", name="Lecture Room 108", capacity=312)],
        students_groups=[],
        courses=[],
        instructors=[],
    )

    response = await authenticated_client.put(
        "/schedule-config/",
        json=config.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    assert response.status_code == 200
    assert response.json()["term"]["name"] == "Spring 2026"
    assert response.json()["rooms"][0]["id"] == "108"
    assert _revision(response.headers["etag"]) == 1


@pytest.mark.asyncio
async def test_put_full_schedule_config_yaml(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    yaml_text = """
term:
  name: Spring 2026
  semester:
    start_date: 2026-06-01
    end_date: 2026-08-02
rooms:
  - id: "108"
    name: Lecture Room 108
    capacity: 312
courses: []
instructors: []
students_groups: []
"""

    response = await authenticated_client.put(
        "/schedule-config/yaml",
        content=yaml_text,
        headers=_yaml_headers(),
    )
    assert response.status_code == 200
    assert response.json()["term"]["name"] == "Spring 2026"
    assert response.json()["rooms"][0]["id"] == "108"


@pytest.mark.asyncio
async def test_put_full_schedule_config_yaml_file(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    yaml_text = """
term:
  name: Spring 2026
  semester:
    start_date: 2026-06-01
    end_date: 2026-08-02
rooms:
  - id: "108"
    name: Lecture Room 108
    capacity: 312
courses: []
instructors: []
students_groups: []
"""

    response = await authenticated_client.put(
        "/schedule-config/yaml-file",
        files={"file": ("config.yaml", yaml_text.encode("utf-8"), "application/x-yaml")},
    )
    assert response.status_code == 200
    assert response.json()["term"]["name"] == "Spring 2026"
    assert response.json()["rooms"][0]["id"] == "108"
    assert _revision(response.headers["etag"]) == 1


@pytest.mark.asyncio
async def test_put_yaml_file_strips_legacy_section_kind(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term_settings())
    with schedule_config_repo._session() as session:
        row = session.get(TermRow, 1)
        assert row is not None
        row.sections = [
            {"code": "core", "name": "Core", "kind": "core", "programs": []},
            {"code": "english", "name": "English", "kind": "english", "programs": []},
            {"code": "electives", "name": "Electives", "kind": "electives", "programs": []},
        ]
        session.add(row)
        session.commit()

    assembled = schedule_config_repo.get_assembled()
    assert [section.model_dump(exclude_none=True) for section in assembled.term.sections] == [
        {"code": "core", "name": "Core", "programs": []},
        {"code": "english", "name": "English", "programs": []},
        {"code": "electives", "name": "Electives", "programs": []},
    ]

    response = await authenticated_client.put(
        "/schedule-config/yaml-file",
        files={
            "file": (
                "config.yaml",
                b"""
term:
  name: Fall 2026
  semester:
    start_date: 2026-08-25
    end_date: 2026-12-24
rooms: []
courses: []
instructors: []
students_groups: []
""",
                "application/x-yaml",
            )
        },
    )
    assert response.status_code == 200
    assert response.json()["term"]["name"] == "Fall 2026"
    assert all("kind" not in section for section in response.json()["term"]["sections"])


@pytest.mark.asyncio
async def test_partial_put_leaves_unspecified_resources_unchanged(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term_settings())
    schedule_config_repo.create_room(RoomConfig.Room(id="108", name="Lecture Room 108", capacity=312))

    response = await authenticated_client.put(
        "/schedule-config/",
        json={"term": _minimal_term().model_copy(update={"name": "Summer 2026"}).model_dump(mode="json")},
    )
    assert response.status_code == 200
    assert response.json()["term"]["name"] == "Summer 2026"
    assert response.json()["rooms"][0]["id"] == "108"


@pytest.mark.asyncio
async def test_put_schedule_config_requires_moderator(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.moderator_emails", ["moderator@innopolis.university"]
    )
    response = await authenticated_client.put(
        "/schedule-config/",
        json={"term": _minimal_term_settings().model_dump(mode="json")},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_instructor_meetings_counts_endpoint(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.moderator_emails", ["moderator@innopolis.university"]
    )
    term = _minimal_term().model_copy(
        update={
            "semester": TermConfig.DateRange(
                start_date=dtm.date(2026, 9, 1),
                end_date=dtm.date(2026, 9, 28),
            ),
            "days": [
                Weekday.MONDAY,
                Weekday.TUESDAY,
                Weekday.WEDNESDAY,
                Weekday.THURSDAY,
                Weekday.FRIDAY,
            ],
        }
    )
    schedule_config_repo.set_term(term)
    schedule_config_repo.set_sections(
        SectionsConfig(
            sections=[
                SectionConfig(
                    code="core",
                    name="Core",
                    programs=[SectionConfig.SectionProgram(code="BS", name="BS", groups=["G1"])],
                )
            ],
            students_groups=[
                StudentsGroups(
                    code="G1",
                )
            ],
        )
    )
    schedule_config_repo.create_instructor(InstructorConfig.Instructor(id="a@iu.ru"))
    schedule_config_repo.create_instructor(InstructorConfig.Instructor(id="b@iu.ru"))
    schedule_config_repo.create_course(
        CourseConfig(
            name="Course",
            section_code="core",
            components=[
                CourseConfig.Component(
                    tag="lab",
                    audience=["G1"],
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
        )
    )

    list_response = await authenticated_client.get("/schedule-config/instructors")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert all("meetings_count" not in instructor for instructor in listed)

    all_counts = await authenticated_client.get("/schedule-config/instructors/meetings-counts")
    assert all_counts.status_code == 200
    assert all_counts.json()["counts"] == {"a@iu.ru": 4, "b@iu.ru": 0}

    selective = await authenticated_client.get(
        "/schedule-config/instructors/meetings-counts",
        params=[("instructor_id", "a@iu.ru")],
    )
    assert selective.status_code == 200
    assert selective.json()["counts"] == {"a@iu.ru": 4}
