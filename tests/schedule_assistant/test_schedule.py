import datetime as dtm

import pytest
from httpx import AsyncClient

from src.schedule_assistant.modules.schedule_config.repository import ScheduleConfigRepository
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    CoursesConfig,
    InstructorConfig,
    SectionConfig,
    SectionsConfig,
    SessionOccurrence,
    StudentsGroups,
    TermConfig,
    WeeklyPatternSlot,
)
from src.schedule_assistant.weekday import Weekday


def _seed_config(repo: ScheduleConfigRepository, *, student_email: str = "test@test.com") -> None:
    repo.set_term(
        TermConfig(
            name="Summer 2026",
            semester=TermConfig.DateRange(
                start_date=dtm.date(2026, 6, 1),
                end_date=dtm.date(2026, 8, 2),
            ),
        ),
        saved_by="mod@innopolis.university",
    )
    repo.set_sections(
        SectionsConfig(
            sections=[
                SectionConfig(
                    code="core",
                    name="Core",
                    programs=[
                        SectionConfig.SectionProgram(
                            code="BS",
                            name="BS",
                            groups=["B25-CSE-01", "SUM26-AAI"],
                        ),
                    ],
                ),
            ],
            students_groups=[
                StudentsGroups(
                    code="B25-CSE-01",
                    kind="core",
                    name="B25-CSE-01",
                    students=[student_email],
                ),
                StudentsGroups(
                    code="SUM26-AAI",
                    kind="elective",
                    name="SUM26-AAI",
                    students=["other@innopolis.university"],
                ),
            ],
        ),
        saved_by="mod@innopolis.university",
    )
    repo.set_instructors(
        InstructorConfig(
            instructors=[
                InstructorConfig.Instructor(
                    id="teacher@innopolis.ru",
                    email="teacher@innopolis.ru",
                    name_en="Teacher One",
                ),
                InstructorConfig.Instructor(
                    id="other@innopolis.ru",
                    email="other@innopolis.ru",
                    name_en="Teacher Two",
                ),
            ],
        ),
        saved_by="mod@innopolis.university",
    )
    repo.set_courses(
        CoursesConfig(
            courses=[
                CourseConfig(
                    name="Agentic AI",
                    section_code="core",
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
                                        SessionOccurrence(
                                            date=dtm.date(2026, 6, 15),
                                            start_time=dtm.time(14, 20),
                                            end_time=dtm.time(15, 50),
                                            room="ONLINE",
                                            instructor="other@innopolis.ru",
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
                CourseConfig(
                    name="Algorithms",
                    section_code="core",
                    components=[
                        CourseConfig.Component(
                            tag="lec",
                            student_groups=["B25-CSE-01"],
                            sessions=[
                                ComponentSessionSeries(
                                    audience=["B25-CSE-01"],
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
            ],
        ),
        saved_by="mod@innopolis.university",
    )


@pytest.mark.asyncio
async def test_my_groups_returns_membership(
    authenticated_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.moderator_emails", ["moderator@innopolis.university"]
    )
    _seed_config(schedule_data_repo)

    response = await authenticated_client.get("/schedule/my-groups")
    assert response.status_code == 200
    assert response.json() == [
        {
            "code": "B25-CSE-01",
            "kind": "core",
            "name": "B25-CSE-01",
            "estimated_size": None,
            "students": ["test@test.com"],
        },
    ]


@pytest.mark.asyncio
async def test_group_schedule_accessible_for_any_authenticated_user(
    authenticated_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.moderator_emails", ["moderator@innopolis.university"]
    )
    _seed_config(schedule_data_repo)

    response = await authenticated_client.get("/schedule/groups/SUM26-AAI")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["courses"]) == 1
    assert payload["courses"][0]["name"] == "Agentic AI"
    assert payload["courses"][0]["components"][0]["sessions"][0]["audience"] == ["SUM26-AAI"]
    assert len(payload["courses"][0]["components"][0]["sessions"][0]["occurrences"]) == 2


@pytest.mark.asyncio
async def test_group_schedule_not_found(
    authenticated_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    _seed_config(schedule_data_repo)

    response = await authenticated_client.get("/schedule/groups/UNKNOWN-GROUP")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_instructor_schedule_returns_only_their_meetings(
    authenticated_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
) -> None:
    _seed_config(schedule_data_repo)

    response = await authenticated_client.get("/schedule/instructors/teacher@innopolis.ru")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["courses"]) == 2
    assert payload["courses"][0]["name"] == "Agentic AI"
    assert len(payload["courses"][0]["components"][0]["sessions"][0]["occurrences"]) == 1
    assert (
        payload["courses"][0]["components"][0]["sessions"][0]["occurrences"][0]["instructor"] == "teacher@innopolis.ru"
    )
    assert payload["courses"][1]["name"] == "Algorithms"
    assert len(payload["courses"][1]["components"][0]["sessions"][0]["weekly_pattern"]) == 1


@pytest.mark.asyncio
async def test_instructor_schedule_requires_exact_id(
    authenticated_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
) -> None:
    _seed_config(schedule_data_repo)

    response = await authenticated_client.get("/schedule/instructors/Teacher%20One")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_instructor_schedule_not_found(
    authenticated_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
) -> None:
    _seed_config(schedule_data_repo)

    response = await authenticated_client.get("/schedule/instructors/unknown@innopolis.ru")
    assert response.status_code == 404
