import datetime as dtm

from src.schedule_assistant.modules.issues.issue_text import (
    format_capacity_issue_text,
    format_instructor_id_issue_text,
    format_meeting_when,
    format_room_issue_text,
    format_unplaced_issue_text,
)
from src.schedule_assistant.modules.issues.schemas import (
    CapacityIssue,
    InstructorIdIssue,
    IssueTypeEnum,
    OccurrencePlacement,
    RoomIssue,
    ScheduledMeeting,
    UnplacedIssue,
    WeeklyPatternPlacement,
)
from src.schedule_assistant.weekday import Weekday


def test_format_meeting_when_weekly() -> None:
    meeting = ScheduledMeeting(
        course_name="Deep Learning for Search",
        component_tag="lec",
        source_kind="core_course",
        placement=WeeklyPatternPlacement(weekday=Weekday.THURSDAY),
        start_time=dtm.time(14, 20),
        end_time=dtm.time(15, 50),
    )
    assert format_meeting_when(meeting, include_time=False) == "в четверг"


def test_format_capacity_issue_text() -> None:
    meeting = ScheduledMeeting(
        course_name="Deep Learning for Search",
        component_tag="lec",
        source_kind="core_course",
        placement=WeeklyPatternPlacement(weekday=Weekday.THURSDAY),
        start_time=dtm.time(14, 20),
        end_time=dtm.time(15, 50),
        room="303",
        students_number=300,
    )
    issue = CapacityIssue(
        issue_type=IssueTypeEnum.CAPACITY,
        room="303",
        room_capacity=30,
        needed_capacity=300,
        meeting=meeting,
    )
    assert (
        format_capacity_issue_text(issue)
        == "300 студентов не могут поместиться в аудиторию 303 (30 человек макс.) во время занятия «Deep Learning for Search» в четверг"
    )


def test_format_room_issue_text() -> None:
    meeting_a = ScheduledMeeting(
        course_name="Course A",
        component_tag="lec",
        source_kind="core_course",
        placement=OccurrencePlacement(date=dtm.date(2026, 6, 8)),
        start_time=dtm.time(14, 20),
        end_time=dtm.time(15, 50),
        room="107",
    )
    meeting_b = ScheduledMeeting(
        course_name="Course B",
        component_tag="lec",
        source_kind="core_course",
        placement=OccurrencePlacement(date=dtm.date(2026, 6, 8)),
        start_time=dtm.time(14, 20),
        end_time=dtm.time(15, 50),
        room="107",
    )
    issue = RoomIssue(
        issue_type=IssueTypeEnum.ROOM,
        room="107",
        meetings=[meeting_a, meeting_b],
    )
    text = format_room_issue_text(issue)
    assert "В аудитории 107" in text
    assert "«Course A»" in text
    assert "«Course B»" in text


def test_format_instructor_id_issue_text() -> None:
    issue = InstructorIdIssue(
        issue_type=IssueTypeEnum.INSTRUCTOR_ID,
        instructor_id="nikolay_kudasov",
    )
    assert (
        format_instructor_id_issue_text(issue)
        == "Идентификатор преподавателя «nikolay_kudasov» должен заканчиваться на @innopolis.ru или @innopolis.university"
    )


def test_format_unplaced_issue_text() -> None:
    issue = UnplacedIssue(
        issue_type=IssueTypeEnum.UNPLACED,
        course_name="Algorithms",
        component_tag="lec",
        source_kind="core_course",
        student_groups=("G1", "G2"),
    )
    assert (
        format_unplaced_issue_text(issue)
        == "Для компонента «lec» курса «Algorithms» (группы G1, G2) не задано расписание"
    )
