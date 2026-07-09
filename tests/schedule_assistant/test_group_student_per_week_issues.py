import datetime as dtm
from unittest.mock import AsyncMock, patch

import pytest

from src.schedule_assistant.modules.issues.checker import IssueChecker
from src.schedule_assistant.modules.issues.per_week import per_week_issues_from_schedule_config
from src.schedule_assistant.modules.issues.schemas import (
    GroupIssue,
    IssueTypeEnum,
    PerWeekIssue,
    ScheduledMeeting,
    StudentIssue,
    WeeklyPatternPlacement,
)
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    CoursesConfig,
    SectionsConfig,
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


def _weekly_meeting(
    *,
    course_name: str,
    start_time: dtm.time,
    end_time: dtm.time,
    room: str,
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
        instructor="teacher@innopolis.ru",
        groups=groups,
        students_number=20,
    )


@pytest.fixture
def issue_checker() -> IssueChecker:
    return IssueChecker(
        courses=CoursesConfig(),
        sections=SectionsConfig(),
        term=_minimal_term(),
        room_to_capacity={"107": 150},
        valid_room_ids={"107"},
    )


def test_group_issue_when_same_group_overlaps(issue_checker: IssueChecker) -> None:
    meetings = [
        _weekly_meeting(
            course_name="Course A",
            start_time=dtm.time(14, 20),
            end_time=dtm.time(15, 50),
            room="107",
            groups=("G1",),
        ),
        _weekly_meeting(
            course_name="Course B",
            start_time=dtm.time(14, 20),
            end_time=dtm.time(15, 50),
            room="108",
            groups=("G1",),
        ),
    ]

    issues = issue_checker.check_for_group_issue(meetings)

    assert len(issues) == 1
    assert isinstance(issues[0], GroupIssue)
    assert issues[0].issue_type == IssueTypeEnum.GROUP
    assert issues[0].group == "G1"
    assert "Группа G1" in issues[0].text


def test_no_group_issue_when_times_differ(issue_checker: IssueChecker) -> None:
    meetings = [
        _weekly_meeting(
            course_name="Course A",
            start_time=dtm.time(14, 20),
            end_time=dtm.time(15, 50),
            room="107",
            groups=("G1",),
        ),
        _weekly_meeting(
            course_name="Course B",
            start_time=dtm.time(16, 0),
            end_time=dtm.time(17, 30),
            room="108",
            groups=("G1",),
        ),
    ]

    assert issue_checker.check_for_group_issue(meetings) == []


def test_student_issue_when_shared_student_overlaps() -> None:
    sections = SectionsConfig(
        students_groups=[
            StudentsGroups(code="G1", kind="core", students=["student@innopolis.ru"]),
            StudentsGroups(code="G2", kind="core", students=["student@innopolis.ru"]),
        ],
    )
    checker = IssueChecker(
        courses=CoursesConfig(),
        sections=sections,
        term=_minimal_term(),
    )
    meetings = [
        _weekly_meeting(
            course_name="Course A",
            start_time=dtm.time(14, 20),
            end_time=dtm.time(15, 50),
            room="107",
            groups=("G1",),
        ),
        _weekly_meeting(
            course_name="Course B",
            start_time=dtm.time(14, 20),
            end_time=dtm.time(15, 50),
            room="108",
            groups=("G2",),
        ),
    ]

    issues = checker.check_for_student_issue(meetings)

    assert len(issues) == 1
    assert isinstance(issues[0], StudentIssue)
    assert issues[0].student == "student@innopolis.ru"
    assert "Студент student@innopolis.ru" in issues[0].text


def test_no_student_issue_without_shared_membership(issue_checker: IssueChecker) -> None:
    meetings = [
        _weekly_meeting(
            course_name="Course A",
            start_time=dtm.time(14, 20),
            end_time=dtm.time(15, 50),
            room="107",
            groups=("G1",),
        ),
        _weekly_meeting(
            course_name="Course B",
            start_time=dtm.time(14, 20),
            end_time=dtm.time(15, 50),
            room="108",
            groups=("G2",),
        ),
    ]

    assert issue_checker.check_for_student_issue(meetings) == []


def test_per_week_issue_when_slot_count_mismatch() -> None:
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Algorithms",
                course_tags=["core_course"],
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        per_week=2,
                        student_groups=["G1"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["G1"],
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.MONDAY,
                                        start_time=dtm.time(9, 0),
                                        end_time=dtm.time(10, 30),
                                        room="107",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    sections = SectionsConfig(students_groups=[StudentsGroups(code="G1", kind="core")])

    issues = per_week_issues_from_schedule_config(courses, sections)

    assert len(issues) == 1
    assert isinstance(issues[0], PerWeekIssue)
    assert issues[0].expected_per_week == 2
    assert issues[0].actual_per_week == 1
    assert "ожидается 2 занятий в неделю" in issues[0].text


def test_no_per_week_issue_when_count_matches() -> None:
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Algorithms",
                course_tags=["core_course"],
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        per_week=1,
                        student_groups=["G1"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["G1"],
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.MONDAY,
                                        start_time=dtm.time(9, 0),
                                        end_time=dtm.time(10, 30),
                                        room="107",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    sections = SectionsConfig(students_groups=[StudentsGroups(code="G1", kind="core")])

    assert per_week_issues_from_schedule_config(courses, sections) == []


@pytest.mark.asyncio
async def test_booking_load_fails_fast() -> None:
    checker = IssueChecker(
        courses=CoursesConfig(),
        sections=SectionsConfig(),
        term=_minimal_term(),
    )
    mock_client = AsyncMock()
    mock_client.get_all_bookings.side_effect = RuntimeError("booking service down")

    with (
        patch("src.schedule_assistant.modules.issues.checker.booking_client", mock_client),
        pytest.raises(RuntimeError, match="booking service down"),
    ):
        await checker._load_booking_snapshot(
            start_date=dtm.date(2026, 6, 1),
            end_date=dtm.date(2026, 8, 2),
        )
