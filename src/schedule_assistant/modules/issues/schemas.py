import datetime as dtm
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from src.schedule_assistant.modules.bookings.client import BookingDTO
from src.schedule_assistant.modules.schedule_config.schemas import WeeklyPatternSlotEdit
from src.schedule_assistant.schema_base import ScheduleAssistantSchema
from src.schedule_assistant.weekday import Weekday


class OccurrencePlacement(ScheduleAssistantSchema):
    kind: Literal["occurrence"] = "occurrence"
    date: dtm.date


class WeeklyPatternPlacement(ScheduleAssistantSchema):
    kind: Literal["weekly_pattern"] = "weekly_pattern"
    weekday: Weekday
    edits: list[WeeklyPatternSlotEdit] = Field(default_factory=list)


MeetingPlacement = Annotated[
    OccurrencePlacement | WeeklyPatternPlacement,
    Field(discriminator="kind"),
]


class ScheduledMeeting(ScheduleAssistantSchema):
    course_name: str
    component_tag: str
    source_kind: Literal["core_course", "elective"]
    placement: MeetingPlacement
    start_time: dtm.time
    end_time: dtm.time
    room: str | None = None
    instructor: str | list[str] | None = None
    groups: tuple[str, ...] = ()
    students_number: int | None = None

    @model_validator(mode="after")
    def validate_time(self) -> Self:
        if not self.start_time < self.end_time:
            raise ValueError("Start time has to be less than end time")
        return self


class IssueTypeEnum(StrEnum):
    ROOM = "room"
    TEACHER = "teacher"
    CAPACITY = "capacity"
    OUTLOOK = "outlook"
    UNPLACED = "unplaced"
    INSTRUCTOR_ID = "instructor_id"
    UNBOOKED = "unbooked"
    GROUP = "group"
    STUDENT = "student"
    PER_WEEK = "per_week"
    INSTRUCTOR_BANNED_SLOT = "instructor_banned_slot"
    INSTRUCTOR_PREFERENCE = "instructor_preference"
    STUDENT_EMAIL = "student_email"


class CapacityIssue(ScheduleAssistantSchema):
    """Занятие не помещается в аудиторию: число студентов превышает вместимость комнаты."""

    issue_type: Literal[IssueTypeEnum.CAPACITY]

    text: str = ""
    room: str
    room_capacity: int | None
    needed_capacity: int

    meeting: ScheduledMeeting


class RoomIssue(ScheduleAssistantSchema):
    """В одной аудитории одновременно запланированы несколько разных занятий."""

    issue_type: Literal[IssueTypeEnum.ROOM]

    text: str = ""
    room: str
    meetings: list[ScheduledMeeting]


class OutlookIssue(ScheduleAssistantSchema):
    """Занятие пересекается по времени с бронированием в Outlook/room-booking."""

    issue_type: Literal[IssueTypeEnum.OUTLOOK]

    text: str = ""
    outlook_event_title: str
    outlook_info: list[BookingDTO]
    meetings: list[ScheduledMeeting]


class TeacherIssue(ScheduleAssistantSchema):
    """Преподаватель одновременно ведёт занятие и учится на другом (или ведёт несколько занятий)."""

    issue_type: Literal[IssueTypeEnum.TEACHER]

    text: str = ""
    instructor: str
    teaching_meetings: list[ScheduledMeeting]
    studying_meetings: list[ScheduledMeeting]


class UnplacedIssue(ScheduleAssistantSchema):
    """Компонент курса объявлен в конфигурации, но для него не задано расписание."""

    issue_type: Literal[IssueTypeEnum.UNPLACED]

    text: str = ""
    course_name: str
    component_tag: str
    source_kind: Literal["core_course", "elective"]
    student_groups: tuple[str, ...] = ()


class InstructorIdIssue(ScheduleAssistantSchema):
    """Идентификатор преподавателя не является корпоративным email Innopolis."""

    issue_type: Literal[IssueTypeEnum.INSTRUCTOR_ID]

    text: str = ""
    instructor_id: str


class StudentEmailIssue(ScheduleAssistantSchema):
    """Email студента в students_groups не является корпоративным адресом Innopolis."""

    issue_type: Literal[IssueTypeEnum.STUDENT_EMAIL]

    text: str = ""
    student_email: str
    groups: tuple[str, ...] = ()


class UnbookedIssue(ScheduleAssistantSchema):
    """Занятие из конфигурации не имеет соответствующего бронирования в Outlook."""

    issue_type: Literal[IssueTypeEnum.UNBOOKED]

    text: str = ""
    meeting: ScheduledMeeting


class GroupIssue(ScheduleAssistantSchema):
    """Одна группа одновременно должна быть на нескольких занятиях."""

    issue_type: Literal[IssueTypeEnum.GROUP]

    text: str = ""
    group: str
    meetings: list[ScheduledMeeting]


class StudentIssue(ScheduleAssistantSchema):
    """Студент из нескольких групп одновременно должен быть на нескольких занятиях."""

    issue_type: Literal[IssueTypeEnum.STUDENT]

    text: str = ""
    student: str
    meetings: list[ScheduledMeeting]


class PerWeekIssue(ScheduleAssistantSchema):
    """Число занятий в неделю не совпадает с per_week в конфигурации компонента."""

    issue_type: Literal[IssueTypeEnum.PER_WEEK]

    text: str = ""
    course_name: str
    component_tag: str
    source_kind: Literal["core_course", "elective"]
    student_groups: tuple[str, ...] = ()
    expected_per_week: int
    actual_per_week: int


class InstructorBannedSlotIssue(ScheduleAssistantSchema):
    """Занятие назначено преподавателю в запрещённую ячейку сетки weekday+slot."""

    issue_type: Literal[IssueTypeEnum.INSTRUCTOR_BANNED_SLOT]

    text: str = ""
    instructor_id: str
    weekday: Weekday
    start_time: dtm.time
    meeting: ScheduledMeeting


class InstructorPreferenceIssue(ScheduleAssistantSchema):
    """Занятие назначено преподавателю в нежелательную (discouraged) ячейку сетки."""

    issue_type: Literal[IssueTypeEnum.INSTRUCTOR_PREFERENCE]

    text: str = ""
    instructor_id: str
    weekday: Weekday
    start_time: dtm.time
    penalty_weight: int
    meeting: ScheduledMeeting


type Issue = Annotated[
    CapacityIssue
    | RoomIssue
    | OutlookIssue
    | TeacherIssue
    | UnplacedIssue
    | InstructorIdIssue
    | StudentEmailIssue
    | UnbookedIssue
    | GroupIssue
    | StudentIssue
    | PerWeekIssue
    | InstructorBannedSlotIssue
    | InstructorPreferenceIssue,
    Field(discriminator="issue_type"),
]


class CheckParameters(ScheduleAssistantSchema):
    check_room: bool = True
    check_teacher: bool = True
    check_capacity: bool = True
    check_group: bool = True
    check_student: bool = True
    check_outlook: bool = False
    check_unbooked: bool = True
    check_unplaced: bool = True
    check_per_week: bool = True
    check_instructor_id: bool = True
    check_student_email: bool = True
    check_instructor_preference: bool = True
    count_touching_room: bool = False
    "Treat back-to-back room slots that only touch at an endpoint as room conflicts"
    count_touching_teacher: bool = False
    "Treat back-to-back teacher slots that only touch at an endpoint as teacher conflicts"
    count_touching_group: bool = False
    "Treat back-to-back group slots that only touch at an endpoint as group conflicts"
    count_touching_student: bool = False
    "Treat back-to-back student slots that only touch at an endpoint as student conflicts"


class CheckResults(ScheduleAssistantSchema):
    issues: list[Issue]


class DateRange(ScheduleAssistantSchema):
    start_date: dtm.date
    end_date: dtm.date

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self
