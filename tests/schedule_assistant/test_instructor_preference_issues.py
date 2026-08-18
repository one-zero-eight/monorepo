import datetime as dtm

from src.schedule_assistant.modules.issues.instructor_preferences import instructor_preference_issues_from_meetings
from src.schedule_assistant.modules.issues.schemas import IssueTypeEnum, ScheduledMeeting, WeeklyPatternPlacement
from src.schedule_assistant.modules.schedule_config.schemas import (
    InstructorConfig,
    InstructorSlotPreferenceEntry,
    InstructorSlotPreferenceLevel,
    TermConfig,
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


def _meeting(weekday: Weekday, start: dtm.time) -> ScheduledMeeting:
    return ScheduledMeeting(
        course_name="Algorithms",
        component_tag="lec",
        placement=WeeklyPatternPlacement(weekday=weekday),
        start_time=start,
        end_time=dtm.time(start.hour + 1, start.minute),
        instructor="alice@innopolis.ru",
    )


def test_instructor_preference_issues_detect_banned_and_discouraged() -> None:
    term = _minimal_term()
    instructors = InstructorConfig(
        instructors=[
            InstructorConfig.Instructor(
                id="alice@innopolis.ru",
                slot_preferences=[
                    InstructorSlotPreferenceEntry(
                        weekday=Weekday.MONDAY,
                        start_time=dtm.time(9, 0),
                        level=InstructorSlotPreferenceLevel.BANNED,
                    ),
                    InstructorSlotPreferenceEntry(
                        weekday=Weekday.TUESDAY,
                        start_time=dtm.time(9, 0),
                        level=InstructorSlotPreferenceLevel.DISCOURAGED,
                    ),
                ],
            )
        ]
    )
    banned_issues = instructor_preference_issues_from_meetings(
        [_meeting(Weekday.MONDAY, dtm.time(9, 0))],
        instructors,
        term,
    )
    assert len(banned_issues) == 1
    assert banned_issues[0].issue_type == IssueTypeEnum.INSTRUCTOR_BANNED_SLOT

    discouraged_issues = instructor_preference_issues_from_meetings(
        [_meeting(Weekday.TUESDAY, dtm.time(9, 0))],
        instructors,
        term,
    )
    assert len(discouraged_issues) == 1
    assert discouraged_issues[0].issue_type == IssueTypeEnum.INSTRUCTOR_PREFERENCE
