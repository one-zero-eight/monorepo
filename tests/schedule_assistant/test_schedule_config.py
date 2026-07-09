import datetime as dtm

import pytest
from httpx import AsyncClient

from src.schedule_assistant.modules.schedule_config.repository import ScheduleConfigRepository
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    InstructorConfig,
    RoomConfig,
    ScheduleConfig,
    SectionsConfig,
    SessionOccurrence,
    StudentsGroups,
    TermConfig,
)


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
    assert (
        await authenticated_client.post(
            "/schedule-config/rooms",
            json=RoomConfig.Room(id="108", name="Lecture Room 108", capacity=312).model_dump(mode="json"),
        )
    ).status_code == 201
    assert (
        await authenticated_client.post("/schedule-config/courses", json={"name": "Empty", "components": []})
    ).status_code == 201
    assert (
        await authenticated_client.post("/schedule-config/instructors", json={"id": "teacher@innopolis.ru"})
    ).status_code == 201

    assembled_response = await authenticated_client.get("/schedule-config/")
    assert assembled_response.status_code == 200
    assembled = ScheduleConfig.model_validate(assembled_response.json())
    assert assembled.term.name == "Spring 2026"
    assert assembled.rooms == [RoomConfig.Room(id="108", name="Lecture Room 108", capacity=312)]
    assert _revision(assembled_response.headers["etag"]) == 4


@pytest.mark.asyncio
async def test_put_term_appends_history_and_snapshot(
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

    history_response = await authenticated_client.get("/schedule-config/history")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 2
    assert history[0]["revision"] == 2
    assert history[0]["saved_by"] == "test@test.com"
    assert history[0]["resources"] == ["term"]

    event_response = await authenticated_client.get(f"/schedule-config/history/{history[0]['id']}")
    assert event_response.status_code == 200
    event = event_response.json()
    assert any(change.get("path") == "/term/name" for change in event["patch"])

    snapshot_response = await authenticated_client.get(f"/schedule-config/history/{history[0]['id']}/snapshot")
    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["term"]["name"] == "Summer 2026"


@pytest.mark.asyncio
async def test_identical_put_does_not_append_history(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term_settings(), saved_by="test@test.com")
    room = RoomConfig.Room(id="108", name="Lecture Room 108", capacity=312)

    first_response = await authenticated_client.post("/schedule-config/rooms", json=room.model_dump(mode="json"))
    assert first_response.status_code == 201
    assert _revision(first_response.headers["etag"]) == 2

    second_response = await authenticated_client.post("/schedule-config/rooms", json=room.model_dump(mode="json"))
    assert second_response.status_code == 409

    history_response = await authenticated_client.get("/schedule-config/history")
    assert history_response.status_code == 200
    assert len(history_response.json()) == 2


@pytest.mark.asyncio
async def test_update_course_leaves_other_resources_unchanged(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term_settings(), saved_by="test@test.com")
    schedule_config_repo.create_room(
        RoomConfig.Room(id="108", name="Lecture Room 108", capacity=312),
        saved_by="test@test.com",
    )
    schedule_config_repo.create_course(CourseConfig(name="Algorithms", components=[]), saved_by="test@test.com")

    response = await authenticated_client.put(
        "/schedule-config/courses/Algorithms",
        json=CourseConfig(name="Algorithms", course_tags=["core_course"], components=[]).model_dump(mode="json"),
    )
    assert response.status_code == 200
    assert response.json()["course_tags"] == ["core_course"]

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
    schedule_config_repo.set_term(_minimal_term_settings(), saved_by="mod@test.com")
    schedule_config_repo.set_sections(
        SectionsConfig(students_groups=[StudentsGroups(code="SUM26-AAI", kind="elective")]),
        saved_by="mod@test.com",
    )
    schedule_config_repo.create_instructor(
        InstructorConfig.Instructor(id="teacher@innopolis.ru", email="teacher@innopolis.ru", name_en="Teacher"),
        saved_by="mod@test.com",
    )
    schedule_config_repo.create_instructor(
        InstructorConfig.Instructor(id="pool@innopolis.ru", email="pool@innopolis.ru", name_en="Pool Only"),
        saved_by="mod@test.com",
    )
    schedule_config_repo.create_course(
        CourseConfig(
            name="Agentic AI",
            course_tags=["elective"],
            components=[
                CourseConfig.Component(
                    tag="class",
                    student_groups=["SUM26-AAI"],
                    sessions=[
                        ComponentSessionSeries(
                            audience=["SUM26-AAI"],
                            occurrences=[
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
        saved_by="mod@test.com",
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
    schedule_config_repo.set_term(_minimal_term_settings(), saved_by="test@test.com")
    schedule_config_repo.create_course(CourseConfig(name="Algorithms", components=[]), saved_by="test@test.com")

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
    schedule_config_repo.set_term(_minimal_term_settings(), saved_by="test@test.com")
    schedule_config_repo.set_sections(
        SectionsConfig(students_groups=[StudentsGroups(code="SUM26-AAI", kind="elective")]),
        saved_by="test@test.com",
    )
    schedule_config_repo.create_instructor(
        InstructorConfig.Instructor(id="teacher@innopolis.ru", email="teacher@innopolis.ru"),
        saved_by="test@test.com",
    )
    schedule_config_repo.create_instructor(
        InstructorConfig.Instructor(id="pool@innopolis.ru", email="pool@innopolis.ru"),
        saved_by="test@test.com",
    )
    schedule_config_repo.create_course(
        CourseConfig(
            name="Agentic AI",
            course_tags=["elective"],
            components=[
                CourseConfig.Component(
                    tag="class",
                    student_groups=["SUM26-AAI"],
                    sessions=[
                        ComponentSessionSeries(
                            audience=["SUM26-AAI"],
                            occurrences=[
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
        saved_by="test@test.com",
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
async def test_partial_put_leaves_unspecified_resources_unchanged(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    schedule_config_repo.set_term(_minimal_term_settings(), saved_by="test@test.com")
    schedule_config_repo.create_room(
        RoomConfig.Room(id="108", name="Lecture Room 108", capacity=312),
        saved_by="test@test.com",
    )

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
