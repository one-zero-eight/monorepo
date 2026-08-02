import datetime as dtm
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from src.schedule_assistant.modules.bookings.client import RoomDTO
from src.schedule_assistant.modules.issues.checker import IssueChecker
from src.schedule_assistant.modules.issues.instructor_ids import (
    instructor_id_issues_from_schedule_config,
    is_valid_instructor_id,
)
from src.schedule_assistant.modules.issues.meetings import (
    meetings_from_schedule_config,
    unplaced_issues_from_schedule_config,
)
from src.schedule_assistant.modules.issues.schemas import (
    InstructorIdIssue,
    IssueTypeEnum,
    OccurrencePlacement,
    RoomIssue,
    ScheduledMeeting,
    UnplacedIssue,
    WeeklyPatternPlacement,
)
from src.schedule_assistant.modules.schedule_config.repository import ScheduleConfigRepository
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    CoursesConfig,
    InstructorConfig,
    RoomConfig,
    SectionsConfig,
    SessionOccurrence,
    StudentsGroups,
    TermConfig,
    WeeklyPatternSlot,
)
from src.schedule_assistant.weekday import Weekday


def _minimal_term() -> TermConfig:
    return TermConfig(
        name="Summer 2026",
        semester=TermConfig.DateRange(
            start_date=dtm.date(2026, 6, 1),
            end_date=dtm.date(2026, 8, 2),
        ),
    )


def _minimal_courses() -> CoursesConfig:
    return CoursesConfig()


def _minimal_sections() -> SectionsConfig:
    return SectionsConfig()


def _weekly_meeting(
    *,
    course_name: str,
    start_time: dtm.time,
    end_time: dtm.time,
    room: str,
    instructor: str,
    groups: tuple[str, ...],
) -> ScheduledMeeting:
    return ScheduledMeeting(
        course_name=course_name,
        component_tag="lec",
        source_kind="core_course",
        placement=WeeklyPatternPlacement(weekday=Weekday.MONDAY),
        start_time=start_time,
        end_time=end_time,
        room=room,
        instructor=instructor,
        groups=groups,
        students_number=20,
    )


@pytest.fixture
def issue_checker() -> IssueChecker:
    return IssueChecker(
        courses=_minimal_courses(),
        sections=_minimal_sections(),
        term=_minimal_term(),
        room_to_capacity={"107": 150},
        valid_room_ids={"107"},
    )


@pytest.mark.parametrize(
    "data, expected_issues",
    [
        (
            [
                _weekly_meeting(
                    course_name="Lesson 1",
                    start_time=dtm.time(14, 20),
                    end_time=dtm.time(15, 50),
                    room="107",
                    instructor="Teacher 1",
                    groups=("Group 1",),
                ),
                _weekly_meeting(
                    course_name="Lesson 2",
                    start_time=dtm.time(14, 20),
                    end_time=dtm.time(15, 50),
                    room="107",
                    instructor="Teacher 2",
                    groups=("Group 2",),
                ),
            ],
            1,
        ),
        (
            [
                _weekly_meeting(
                    course_name="Lesson 1",
                    start_time=dtm.time(17, 20),
                    end_time=dtm.time(18, 50),
                    room="107",
                    instructor="Teacher 1",
                    groups=("Group 1",),
                ),
                _weekly_meeting(
                    course_name="Lesson 2",
                    start_time=dtm.time(14, 20),
                    end_time=dtm.time(15, 50),
                    room="107",
                    instructor="Teacher 2",
                    groups=("Group 2",),
                ),
            ],
            0,
        ),
    ],
)
def test_room_issues(issue_checker: IssueChecker, data: list[ScheduledMeeting], expected_issues: int) -> None:
    issues = issue_checker.check_for_room_issue(data)
    assert len(issues) == expected_issues
    if expected_issues > 0:
        issue = issues[0]
        assert isinstance(issue, RoomIssue)
        assert issue.issue_type == IssueTypeEnum.ROOM
        assert len(issue.meetings) >= 2


def test_touching_room_slots_ignored_by_default(issue_checker: IssueChecker) -> None:
    data = [
        _weekly_meeting(
            course_name="Introduction to AI (lab)",
            start_time=dtm.time(12, 50),
            end_time=dtm.time(14, 20),
            room="314",
            instructor="Teacher 1",
            groups=("Group 1",),
        ),
        _weekly_meeting(
            course_name="Computer Architecture (lab)",
            start_time=dtm.time(14, 20),
            end_time=dtm.time(15, 50),
            room="314",
            instructor="Teacher 2",
            groups=("Group 2",),
        ),
    ]
    assert issue_checker.check_for_room_issue(data) == []
    assert len(issue_checker.check_for_room_issue(data, count_touching=True)) == 1


def test_meetings_from_schedule_config() -> None:
    sections = SectionsConfig(students_groups=[StudentsGroups(code="SUM26-AAI", kind="elective", estimated_size=25)])
    courses = CoursesConfig(
        courses=[
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
                                        room="107",
                                        instructor="teacher@innopolis.ru",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            CourseConfig(
                name="Algorithms",
                course_tags=["core_course"],
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
                                        room="108",
                                        instructor="other@innopolis.ru",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    meetings = meetings_from_schedule_config(courses, sections)
    assert len(meetings) == 2

    occurrence_placement = meetings[0].placement
    assert isinstance(occurrence_placement, OccurrencePlacement)
    assert occurrence_placement.date == dtm.date(2026, 6, 8)
    assert meetings[0].instructor == "teacher@innopolis.ru"

    weekly_placement = meetings[1].placement
    assert isinstance(weekly_placement, WeeklyPatternPlacement)
    assert weekly_placement.weekday == Weekday.MONDAY


@pytest.mark.parametrize(
    "instructor_id, expected",
    [
        ("teacher@innopolis.ru", True),
        ("Teacher@Innopolis.University", True),
        ("nikolay_kudasov", False),
        ("teacher@gmail.com", False),
    ],
)
def test_is_valid_instructor_id(instructor_id: str, expected: bool) -> None:
    assert is_valid_instructor_id(instructor_id) is expected


def test_instructor_id_issues_from_schedule_config() -> None:
    instructors = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(id="teacher@innopolis.ru"),
            InstructorConfig.Instructor(id="bad_handle"),
        ],
    )
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Course",
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        instructor_pool=["also-bad@gmail.com"],
                    ),
                ],
            ),
        ],
    )

    issues = instructor_id_issues_from_schedule_config(instructors, courses)
    assert len(issues) == 2
    assert all(isinstance(issue, InstructorIdIssue) for issue in issues)
    assert {issue.instructor_id for issue in issues} == {"also-bad@gmail.com", "bad_handle"}


def test_co_teaching_produces_single_meeting() -> None:
    sections = SectionsConfig(students_groups=[StudentsGroups(code="G1", kind="core", estimated_size=10)])
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Co-taught Course",
                course_tags=["core_course"],
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        student_groups=["G1"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["G1"],
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.MONDAY,
                                        start_time=dtm.time(9, 0),
                                        end_time=dtm.time(10, 30),
                                        room="108",
                                        instructor=["teacher-a@innopolis.ru", "teacher-b@innopolis.ru"],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    meetings = meetings_from_schedule_config(courses, sections)
    assert len(meetings) == 1
    assert meetings[0].instructor == ["teacher-a@innopolis.ru", "teacher-b@innopolis.ru"]


def test_unplaced_issues_from_schedule_config() -> None:
    sections = SectionsConfig(students_groups=[StudentsGroups(code="G1", kind="core", estimated_size=10)])

    courses_no_sessions = CoursesConfig(
        courses=[
            CourseConfig(
                name="Unplaced Course",
                course_tags=["core_course"],
                components=[
                    CourseConfig.Component(tag="lec", student_groups=["G1"]),
                ],
            ),
        ],
    )
    issues = unplaced_issues_from_schedule_config(courses_no_sessions, sections)
    assert len(issues) == 1
    assert isinstance(issues[0], UnplacedIssue)
    assert issues[0].issue_type == IssueTypeEnum.UNPLACED
    assert issues[0].course_name == "Unplaced Course"
    assert issues[0].student_groups == ("G1",)

    courses_empty_session = CoursesConfig(
        courses=[
            CourseConfig(
                name="Partial Course",
                components=[
                    CourseConfig.Component(
                        tag="lab",
                        student_groups=["G1"],
                        sessions=[
                            ComponentSessionSeries(audience=["G1"]),
                            ComponentSessionSeries(
                                audience=["G1"],
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.MONDAY,
                                        start_time=dtm.time(9, 0),
                                        end_time=dtm.time(10, 30),
                                        room="108",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    issues = unplaced_issues_from_schedule_config(courses_empty_session, sections)
    assert len(issues) == 1
    assert issues[0].component_tag == "lab"


@pytest.mark.asyncio
async def test_issues_check_endpoint(
    authenticated_client: AsyncClient,
    issues_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    issues_repo.set_term(
        TermConfig(
            name="Summer 2026",
            semester=TermConfig.DateRange(
                start_date=dtm.date(2026, 6, 1),
                end_date=dtm.date(2026, 8, 2),
            ),
        ),
        saved_by="test@test.com",
    )
    issues_repo.set_sections(
        SectionsConfig(students_groups=[StudentsGroups(code="G1", kind="core", estimated_size=10)]),
        saved_by="test@test.com",
    )
    issues_repo.set_rooms(
        RoomConfig(rooms=[RoomConfig.Room(id="107", name="Room 107", capacity=20)]),
        saved_by="test@test.com",
    )
    issues_repo.set_instructors(
        InstructorConfig(
            instructors=[
                InstructorConfig.Instructor(id="t1@innopolis.ru"),
                InstructorConfig.Instructor(id="t2@innopolis.ru"),
            ],
        ),
        saved_by="test@test.com",
    )
    issues_repo.set_courses(
        CoursesConfig(
            courses=[
                CourseConfig(
                    name="Course A",
                    components=[
                        CourseConfig.Component(
                            tag="lec",
                            student_groups=["G1"],
                            sessions=[
                                ComponentSessionSeries(
                                    audience=["G1"],
                                    occurrences=[
                                        SessionOccurrence(
                                            date=dtm.date(2026, 6, 8),
                                            start_time=dtm.time(14, 20),
                                            end_time=dtm.time(15, 50),
                                            room="107",
                                            instructor="t1@innopolis.ru",
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
                CourseConfig(
                    name="Course B",
                    components=[
                        CourseConfig.Component(
                            tag="lec",
                            student_groups=["G1"],
                            sessions=[
                                ComponentSessionSeries(
                                    audience=["G1"],
                                    occurrences=[
                                        SessionOccurrence(
                                            date=dtm.date(2026, 6, 8),
                                            start_time=dtm.time(14, 20),
                                            end_time=dtm.time(15, 50),
                                            room="107",
                                            instructor="t2@innopolis.ru",
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        saved_by="test@test.com",
    )

    mock_client = AsyncMock()
    mock_client.get_rooms.return_value = [
        RoomDTO(
            id="107",
            title="Room 107",
            short_name="107",
            my_uni_id=107,
            capacity=20,
            access_level="red",
            restrict_daytime=False,
        ),
    ]
    mock_client.get_all_bookings.return_value = []
    mock_client.get_auto_bookings.return_value = []

    with patch("src.schedule_assistant.modules.issues.service.booking_client", mock_client):
        response = await authenticated_client.post("/issues/check", json={"check_unbooked": False})

    assert response.status_code == 200
    issues = response.json()["issues"]
    issue_types = {issue["issue_type"] for issue in issues}
    assert issue_types == {"room", "group"}

    room_issue = next(issue for issue in issues if issue["issue_type"] == "room")
    assert len(room_issue["meetings"]) >= 2
    assert room_issue["meetings"][0]["placement"]["kind"] == "occurrence"
    assert "В аудитории 107" in room_issue["text"]

    group_issue = next(issue for issue in issues if issue["issue_type"] == "group")
    assert group_issue["group"] == "G1"
    assert "Группа G1" in group_issue["text"]
