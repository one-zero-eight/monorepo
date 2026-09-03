import datetime as dtm
from typing import Any, cast

import icalendar
import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from src.schedule_assistant.modules.schedule import service
from src.schedule_assistant.modules.schedule.ics import teacher_alias
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
    WeeklyPatternSlotEdit,
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
                            groups=["CORE-ONLY"],
                        ),
                    ],
                ),
                SectionConfig(
                    code="english",
                    name="Английский",
                    programs=[
                        SectionConfig.SectionProgram(
                            code="ENGLISH",
                            name="English",
                            groups=["B25-CSE-01"],
                            tracks=[
                                SectionConfig.SectionProgram.ProgramTrack(
                                    code="AAI",
                                    name="AAI",
                                    groups=["SUM26-AAI", "SUM26-AAI"],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
            students_groups=[
                StudentsGroups(
                    code="B25-CSE-01",
                    name="B25-CSE-01",
                    students=[student_email],
                ),
                StudentsGroups(
                    code="SUM26-AAI",
                    name="SUM26-AAI",
                    students=["other@innopolis.university"],
                ),
                StudentsGroups(code="CORE-ONLY", name="CORE-ONLY"),
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
                    email="other@innopolis.university",
                    name_en="Teacher Two",
                ),
                InstructorConfig.Instructor(
                    id="unscheduled@innopolis.ru",
                    email="unscheduled@innopolis.ru",
                    name_en="Unscheduled Teacher",
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
                    section_code="english",
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
                    section_code="english",
                    components=[
                        CourseConfig.Component(
                            tag="lec",
                            audience=["B25-CSE-01"],
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
    assert len(payload["courses"][0]["components"][0]["sessions"][0]["dates_pattern"]) == 2


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
    assert len(payload["courses"][0]["components"][0]["sessions"][0]["dates_pattern"]) == 1
    assert (
        payload["courses"][0]["components"][0]["sessions"][0]["dates_pattern"][0]["instructor"]
        == "teacher@innopolis.ru"
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


def _service_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-schedule-assistant-api-key"}


def test_teacher_alias_only_strips_email() -> None:
    assert teacher_alias(" Teacher@Innopolis.RU ") == "teacher-Teacher@Innopolis.RU"
    assert teacher_alias("Teacher@Innopolis.RU") != teacher_alias("teacher@innopolis.ru")


@pytest.mark.asyncio
async def test_virtual_event_groups_require_service_api_key(
    fastapi_test_client: AsyncClient,
) -> None:
    response = await fastapi_test_client.get("/integration/event-groups")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_virtual_event_groups_publish_english_section_groups(
    fastapi_test_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_config(schedule_data_repo)
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.api_key",
        SecretStr("test-schedule-assistant-api-key"),
    )
    response = await fastapi_test_client.get("/integration/event-groups", headers=_service_headers())
    assert response.status_code == 200
    assert response.json() == {
        "event_groups": [
            {
                "id": None,
                "alias": "english-b25-cse-01",
                "name": "B25-CSE-01",
                "description": "Schedule for B25-CSE-01",
                "group_code": "B25-CSE-01",
                "instructor_id": None,
            },
            {
                "id": None,
                "alias": "english-sum26-aai",
                "name": "SUM26-AAI",
                "description": "Schedule for SUM26-AAI",
                "group_code": "SUM26-AAI",
                "instructor_id": None,
            },
            {
                "id": None,
                "alias": teacher_alias("other@innopolis.university"),
                "name": "Teacher Two",
                "description": "Schedule for Teacher Two",
                "group_code": None,
                "instructor_id": "other@innopolis.ru",
            },
            {
                "id": None,
                "alias": teacher_alias("teacher@innopolis.ru"),
                "name": "Teacher One",
                "description": "Schedule for Teacher One",
                "group_code": None,
                "instructor_id": "teacher@innopolis.ru",
            },
        ]
    }


@pytest.mark.asyncio
async def test_missing_english_section_publishes_no_student_groups(
    fastapi_test_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
) -> None:
    _seed_config(schedule_data_repo)
    sections = schedule_data_repo.get_sections()
    sections.sections = [section for section in sections.sections if section.code != "english"]
    schedule_data_repo.set_sections(sections, saved_by="test")

    response = await fastapi_test_client.get("/integration/event-groups", headers=_service_headers())
    assert response.status_code == 200
    assert [group["alias"] for group in response.json()["event_groups"]] == [
        teacher_alias("other@innopolis.university"),
        teacher_alias("teacher@innopolis.ru"),
    ]


@pytest.mark.asyncio
async def test_predefined_aliases_normalize_email(
    fastapi_test_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
) -> None:
    _seed_config(schedule_data_repo, student_email=" Student@Innopolis.University ")

    response = await fastapi_test_client.get(
        "/integration/users/student@innopolis.university/predefined",
        headers=_service_headers(),
    )
    assert response.status_code == 200
    assert response.json() == {"event_groups": ["english-b25-cse-01"]}

    response = await fastapi_test_client.get(
        "/integration/users/OTHER@INNOPOLIS.UNIVERSITY/predefined",
        headers=_service_headers(),
    )
    assert response.status_code == 200
    assert response.json() == {
        "event_groups": [
            "english-sum26-aai",
            teacher_alias("other@innopolis.university"),
        ]
    }

    response = await fastapi_test_client.get(
        "/integration/users/TEACHER@INNOPOLIS.RU/predefined",
        headers=_service_headers(),
    )
    assert response.status_code == 200
    assert response.json() == {"event_groups": [teacher_alias("teacher@innopolis.ru")]}


@pytest.mark.asyncio
async def test_instructor_ics_contains_only_matching_meetings(
    fastapi_test_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_config(schedule_data_repo)
    alias = teacher_alias("teacher@innopolis.ru")
    original_get_instructors = schedule_data_repo.get_instructors
    get_instructors_calls = 0

    def count_get_instructors_calls() -> InstructorConfig:
        nonlocal get_instructors_calls
        get_instructors_calls += 1
        return original_get_instructors()

    monkeypatch.setattr(schedule_data_repo, "get_instructors", count_get_instructors_calls)

    response = await fastapi_test_client.get(
        f"/integration/event-groups/{alias}/schedule.ics",
        headers=_service_headers(),
    )

    assert response.status_code == 200
    calendar = icalendar.Calendar.from_ical(response.text)
    events = [cast(icalendar.Event, component) for component in calendar.walk("VEVENT")]
    assert len(events) == 2
    assert {str(event["summary"]) for event in events} == {
        "Agentic AI (class)",
        "Algorithms (lec)",
    }
    assert {str(event["description"]).splitlines()[0] for event in events} == {"Instructor: Teacher One"}
    recurring_events = [event for event in events if event.get("RRULE")]
    assert len(recurring_events) == 1
    assert cast(Any, recurring_events[0]["RRULE"])["FREQ"] == ["WEEKLY"]
    assert get_instructors_calls == 2


@pytest.mark.asyncio
async def test_batch_aliases_ics_deduplicates_student_and_instructor_match(
    fastapi_test_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
) -> None:
    _seed_config(schedule_data_repo)

    response = await fastapi_test_client.post(
        "/integration/event-groups/schedule.ics",
        json={
            "aliases": [
                "english-sum26-aai",
                teacher_alias("teacher@innopolis.ru"),
            ]
        },
        headers=_service_headers(),
    )

    assert response.status_code == 200
    calendar = icalendar.Calendar.from_ical(response.text)
    events = [cast(icalendar.Event, component) for component in calendar.walk("VEVENT")]
    assert len(events) == 3
    matching_agentic_events = [
        event
        for event in events
        if str(event["summary"]) == "Agentic AI (class)" and "Instructor: Teacher One" in str(event["description"])
    ]
    assert len(matching_agentic_events) == 1


@pytest.mark.asyncio
async def test_group_ics_is_valid_and_deterministic(
    fastapi_test_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
) -> None:
    _seed_config(schedule_data_repo)

    first = await fastapi_test_client.get(
        "/integration/event-groups/english-sum26-aai/schedule.ics",
        headers=_service_headers(),
    )
    second = await fastapi_test_client.get(
        "/integration/event-groups/english-sum26-aai/schedule.ics",
        headers=_service_headers(),
    )
    assert first.status_code == 200
    assert first.content == second.content
    calendar = icalendar.Calendar.from_ical(first.text)
    events = [cast(icalendar.Event, component) for component in calendar.walk("VEVENT")]
    assert len(events) == 2
    assert {str(event["summary"]) for event in events} == {"Agentic AI (class)"}
    assert {str(event["location"]) for event in events} == {"ONLINE"}
    assert {str(event["description"]).splitlines()[0] for event in events} == {
        "Instructor: Teacher One",
        "Instructor: Teacher Two",
    }
    assert all(event.decoded("dtstart").tzname() == "MSK" for event in events)
    assert all(event.decoded("dtstart").utcoffset() == dtm.timedelta(hours=3) for event in events)
    assert len({str(event["uid"]) for event in events}) == 2


def test_group_ics_handles_database_times_with_mixed_timezone_awareness(
    schedule_data_repo: ScheduleConfigRepository,
) -> None:
    _seed_config(schedule_data_repo)
    courses = schedule_data_repo.get_courses()
    algorithms_component = courses.courses[1].components[0]
    assert algorithms_component.sessions is not None
    algorithms_session = algorithms_component.sessions[0]
    assert algorithms_session.weekly_pattern is not None
    slot = algorithms_session.weekly_pattern[0]
    slot.start_time = slot.start_time.replace(tzinfo=dtm.timezone(dtm.timedelta(hours=3)))
    schedule_data_repo.set_courses(courses, saved_by="test")

    calendar = icalendar.Calendar.from_ical(service.get_group_ics("english-b25-cse-01"))
    events = [cast(icalendar.Event, component) for component in calendar.walk("VEVENT")]

    assert events
    assert all(event.decoded("dtstart").utcoffset() == dtm.timedelta(hours=3) for event in events)


def test_weekly_ics_uses_rrule_exdate_and_recurrence_override(
    schedule_data_repo: ScheduleConfigRepository,
) -> None:
    _seed_config(schedule_data_repo)
    courses = schedule_data_repo.get_courses()
    sessions = courses.courses[1].components[0].sessions
    assert sessions is not None
    weekly_pattern = sessions[0].weekly_pattern
    assert weekly_pattern is not None
    weekly_slot = weekly_pattern[0]
    weekly_slot.edits = [
        WeeklyPatternSlotEdit(
            select_week=dtm.date(2026, 6, 8),
            cancel=True,
        ),
        WeeklyPatternSlotEdit(
            select_week=dtm.date(2026, 6, 15),
            date=dtm.date(2026, 6, 16),
            start_time=dtm.time(10, 40),
            end_time=dtm.time(12, 10),
            room="ONLINE",
            instructor="other@innopolis.ru",
        ),
    ]
    schedule_data_repo.set_courses(courses, saved_by="test")

    calendar = icalendar.Calendar.from_ical(service.get_group_ics("english-b25-cse-01"))
    events = [cast(icalendar.Event, component) for component in calendar.walk("VEVENT")]

    assert len(events) == 2
    recurring = next(event for event in events if event.get("RRULE"))
    override = next(event for event in events if event.get("RECURRENCE-ID"))
    assert cast(Any, recurring["RRULE"])["FREQ"] == ["WEEKLY"]
    exdates = cast(Any, recurring["EXDATE"])
    assert not isinstance(exdates, list)
    assert len(exdates.dts) == 1
    assert override.decoded("dtstart").date() == dtm.date(2026, 6, 16)
    assert override.decoded("dtstart").time() == dtm.time(10, 40)
    assert override.decoded("recurrence-id").date() == dtm.date(2026, 6, 15)
    assert str(override["location"]) == "ONLINE"
    assert str(override["description"]).splitlines()[0] == "Instructor: Teacher Two"


@pytest.mark.asyncio
async def test_batch_aliases_ics_combines_selected_groups(
    fastapi_test_client: AsyncClient,
    schedule_data_repo: ScheduleConfigRepository,
) -> None:
    _seed_config(schedule_data_repo)

    response = await fastapi_test_client.post(
        "/integration/event-groups/schedule.ics",
        json={
            "aliases": [
                "english-sum26-aai",
                "english-b25-cse-01",
                "english-sum26-aai",
            ]
        },
        headers=_service_headers(),
    )
    assert response.status_code == 200
    calendar = icalendar.Calendar.from_ical(response.text)
    events = [component for component in calendar.walk("VEVENT")]
    assert len(events) == 3
    assert {str(event["summary"]) for event in events} == {
        "Agentic AI (class)",
        "Algorithms (lec)",
    }
