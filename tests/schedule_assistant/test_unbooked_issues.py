import datetime as dtm
from unittest.mock import AsyncMock, patch

import pytest

from src.schedule_assistant.modules.bookings.client import BookingDTO
from src.schedule_assistant.modules.issues.checker import IssueChecker
from src.schedule_assistant.modules.issues.schemas import IssueTypeEnum, UnbookedIssue
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    CoursesConfig,
    SectionsConfig,
    SessionOccurrence,
    StudentsGroups,
    TermConfig,
)


def _checker(courses: CoursesConfig) -> IssueChecker:
    return IssueChecker(
        courses=courses,
        sections=SectionsConfig(students_groups=[StudentsGroups(code="G1", kind="core", estimated_size=10)]),
        term=TermConfig(
            name="Summer 2026",
            semester=TermConfig.DateRange(
                start_date=dtm.date(2026, 6, 1),
                end_date=dtm.date(2026, 8, 2),
            ),
        ),
        valid_room_ids={"107"},
    )


@pytest.mark.asyncio
async def test_unbooked_issue_when_no_matching_booking() -> None:
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Algorithms",
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
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    checker = _checker(courses)
    mock_client = AsyncMock()
    mock_client.get_all_bookings.return_value = []
    mock_client.get_auto_bookings.return_value = []

    with patch("src.schedule_assistant.modules.issues.checker.booking_client", mock_client):
        bookings = await checker._load_booking_snapshot(
            start_date=dtm.date(2026, 6, 1),
            end_date=dtm.date(2026, 8, 2),
            now=dtm.datetime(2026, 6, 1, tzinfo=dtm.timezone(dtm.timedelta(hours=3))),
        )
        issues = checker.check_for_unbooked_issue(bookings=bookings)

    assert len(issues) == 1
    assert isinstance(issues[0], UnbookedIssue)
    assert issues[0].issue_type == IssueTypeEnum.UNBOOKED
    assert issues[0].meeting.course_name == "Algorithms"
    assert "нет бронирования" in issues[0].text


@pytest.mark.asyncio
async def test_no_unbooked_issue_when_booking_matches() -> None:
    courses = CoursesConfig(
        courses=[
            CourseConfig(
                name="Algorithms",
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
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    checker = _checker(courses)
    mock_client = AsyncMock()
    mock_client.get_all_bookings.return_value = [
        BookingDTO.model_validate(
            {
                "room_id": "107",
                "title": "Schedule Assistant IU Auto: Algorithms (lec)",
                "start": "2026-06-08T14:20:00+03:00",
                "end": "2026-06-08T15:50:00+03:00",
                "categories": ["Auto", "core", "G1", "Algorithms"],
            },
        ),
    ]
    mock_client.get_auto_bookings.return_value = []

    with patch("src.schedule_assistant.modules.issues.checker.booking_client", mock_client):
        bookings = await checker._load_booking_snapshot(
            start_date=dtm.date(2026, 6, 1),
            end_date=dtm.date(2026, 8, 2),
            now=dtm.datetime(2026, 6, 1, tzinfo=dtm.timezone(dtm.timedelta(hours=3))),
        )
        issues = checker.check_for_unbooked_issue(bookings=bookings)

    assert issues == []
