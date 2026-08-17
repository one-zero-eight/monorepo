import datetime as dtm

from src.schedule_assistant.modules.issues.schemas import (
    CapacityIssue,
    GroupIssue,
    InstructorBannedSlotIssue,
    InstructorIdIssue,
    InstructorPreferenceIssue,
    MissingInstructorIssue,
    MissingRoomIssue,
    OccurrencePlacement,
    OutlookIssue,
    PerWeekIssue,
    RoomIssue,
    ScheduledMeeting,
    StudentEmailIssue,
    StudentIssue,
    TeacherIssue,
    UnbookedIssue,
    UnplacedIssue,
    WeeklyPatternPlacement,
)
from src.schedule_assistant.weekday import Weekday

_WEEKDAY_WHEN_RU: dict[Weekday, str] = {
    Weekday.MONDAY: "в понедельник",
    Weekday.TUESDAY: "во вторник",
    Weekday.WEDNESDAY: "в среду",
    Weekday.THURSDAY: "в четверг",
    Weekday.FRIDAY: "в пятницу",
    Weekday.SATURDAY: "в субботу",
    Weekday.SUNDAY: "в воскресенье",
}

_MONTH_GENITIVE_RU = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def _format_time(value: dtm.time) -> str:
    return value.strftime("%H:%M")


def _format_time_range(start_time: dtm.time, end_time: dtm.time) -> str:
    return f"{_format_time(start_time)}–{_format_time(end_time)}"


def _format_date(date: dtm.date) -> str:
    return f"{date.day} {_MONTH_GENITIVE_RU[date.month - 1]} {date.year}"


def format_meeting_when(meeting: ScheduledMeeting, *, include_time: bool = True) -> str:
    placement = meeting.placement
    time_suffix = f" в {_format_time_range(meeting.start_time, meeting.end_time)}" if include_time else ""

    if isinstance(placement, OccurrencePlacement):
        return f"{_format_date(placement.date)}{time_suffix}"

    assert isinstance(placement, WeeklyPatternPlacement)
    return f"{_WEEKDAY_WHEN_RU[placement.weekday]}{time_suffix}"


def _quoted_course_names(meetings: list[ScheduledMeeting]) -> str:
    names = sorted({meeting.course_name for meeting in meetings})
    return ", ".join(f"«{name}»" for name in names)


def _format_room_with_capacity(room: str, room_capacity: int | None) -> str:
    if room_capacity is None:
        return room
    return f"{room} ({room_capacity} человек макс.)"


def format_capacity_issue_text(issue: CapacityIssue) -> str:
    meeting = issue.meeting
    when = format_meeting_when(meeting, include_time=False)
    room = _format_room_with_capacity(issue.room, issue.room_capacity)
    return (
        f"{issue.needed_capacity} студентов не могут поместиться в аудиторию {room} "
        f"во время занятия «{meeting.course_name}» {when}"
    )


def format_room_issue_text(issue: RoomIssue) -> str:
    when_parts = sorted({format_meeting_when(meeting) for meeting in issue.meetings})
    when = when_parts[0] if len(when_parts) == 1 else "; ".join(when_parts)
    courses = _quoted_course_names(issue.meetings)
    return f"В аудитории {issue.room} одновременно запланированы занятия {courses} {when}"


def format_teacher_issue_text(issue: TeacherIssue) -> str:
    when_parts: set[str] = set()
    for meeting in issue.teaching_meetings + issue.studying_meetings:
        when_parts.add(format_meeting_when(meeting))

    when = next(iter(when_parts)) if len(when_parts) == 1 else "; ".join(sorted(when_parts))
    parts: list[str] = []
    if issue.teaching_meetings:
        parts.append(f"ведёт {_quoted_course_names(issue.teaching_meetings)}")
    if issue.studying_meetings:
        parts.append(f"учится на {_quoted_course_names(issue.studying_meetings)}")
    action = " и ".join(parts)
    return f"Преподаватель {issue.instructor} одновременно {action} {when}"


def format_outlook_issue_text(issue: OutlookIssue) -> str:
    courses = _quoted_course_names(issue.meetings)
    rooms = sorted({meeting.room for meeting in issue.meetings if meeting.room})
    room_part = f"в аудитории {rooms[0]}" if len(rooms) == 1 else f"в аудиториях {', '.join(rooms)}"
    when_parts = sorted({format_meeting_when(meeting) for meeting in issue.meetings})
    when = when_parts[0] if len(when_parts) == 1 else "; ".join(when_parts)
    return f"Занятия {courses} {room_part} пересекаются с бронированием «{issue.outlook_event_title}» {when}"


def format_instructor_id_issue_text(issue: InstructorIdIssue) -> str:
    return (
        f"Идентификатор преподавателя «{issue.instructor_id}» должен заканчиваться "
        f"на @innopolis.ru или @innopolis.university"
    )


def format_student_email_issue_text(issue: StudentEmailIssue) -> str:
    groups_part = ""
    if issue.groups:
        groups_part = f" (группы {', '.join(issue.groups)})"
    return (
        f"Email студента «{issue.student_email}»{groups_part} должен заканчиваться "
        f"на @innopolis.ru или @innopolis.university"
    )


def format_unbooked_issue_text(issue: UnbookedIssue) -> str:
    meeting = issue.meeting
    when = format_meeting_when(meeting)
    room = meeting.room or "—"
    return f"Для занятия «{meeting.course_name}» ({meeting.component_tag}) {when} в аудитории {room} нет бронирования"


def format_group_issue_text(issue: GroupIssue) -> str:
    when_parts = sorted({format_meeting_when(meeting) for meeting in issue.meetings})
    when = when_parts[0] if len(when_parts) == 1 else "; ".join(when_parts)
    courses = _quoted_course_names(issue.meetings)
    return f"Группа {issue.group} одновременно должна быть на занятиях {courses} {when}"


def format_student_issue_text(issue: StudentIssue) -> str:
    when_parts = sorted({format_meeting_when(meeting) for meeting in issue.meetings})
    when = when_parts[0] if len(when_parts) == 1 else "; ".join(when_parts)
    courses = _quoted_course_names(issue.meetings)
    return f"Студент {issue.student} одновременно должен быть на занятиях {courses} {when}"


def format_per_week_issue_text(issue: PerWeekIssue) -> str:
    groups_part = ""
    if issue.student_groups:
        groups = ", ".join(issue.student_groups)
        groups_part = f" (группы {groups})"
    return (
        f"Для компонента «{issue.component_tag}» курса «{issue.course_name}»{groups_part} "
        f"ожидается {issue.expected_per_week} занятий в неделю, задано {issue.actual_per_week}"
    )


def format_instructor_banned_slot_issue_text(issue: InstructorBannedSlotIssue) -> str:
    when = format_meeting_when(issue.meeting)
    return (
        f"Преподаватель {issue.instructor_id} назначен на запрещённый слот "
        f"{_WEEKDAY_WHEN_RU[issue.weekday]} в {_format_time(issue.start_time)} "
        f"для занятия «{issue.meeting.course_name}» ({when})"
    )


def format_instructor_preference_issue_text(issue: InstructorPreferenceIssue) -> str:
    when = format_meeting_when(issue.meeting)
    return (
        f"Преподаватель {issue.instructor_id} назначен на нежелательный слот "
        f"{_WEEKDAY_WHEN_RU[issue.weekday]} в {_format_time(issue.start_time)} "
        f"для занятия «{issue.meeting.course_name}» ({when})"
    )


def format_unplaced_issue_text(issue: UnplacedIssue) -> str:
    groups_part = ""
    if issue.student_groups:
        groups = ", ".join(issue.student_groups)
        groups_part = f" (группы {groups})"
    return f"Для компонента «{issue.component_tag}» курса «{issue.course_name}»{groups_part} не задано расписание"


def format_missing_room_issue_text(issue: MissingRoomIssue) -> str:
    meeting = issue.meeting
    when = format_meeting_when(meeting)
    return f"Для занятия «{meeting.course_name}» ({meeting.component_tag}) {when} не назначена локация"


def format_missing_instructor_issue_text(issue: MissingInstructorIssue) -> str:
    meeting = issue.meeting
    when = format_meeting_when(meeting)
    return f"Для занятия «{meeting.course_name}» ({meeting.component_tag}) {when} не назначен преподаватель"


def attach_issue_text(
    issue: CapacityIssue
    | RoomIssue
    | OutlookIssue
    | TeacherIssue
    | UnplacedIssue
    | MissingRoomIssue
    | MissingInstructorIssue
    | InstructorIdIssue
    | StudentEmailIssue
    | UnbookedIssue
    | GroupIssue
    | StudentIssue
    | PerWeekIssue
    | InstructorBannedSlotIssue
    | InstructorPreferenceIssue,
) -> None:
    if isinstance(issue, CapacityIssue):
        issue.text = format_capacity_issue_text(issue)
    elif isinstance(issue, RoomIssue):
        issue.text = format_room_issue_text(issue)
    elif isinstance(issue, TeacherIssue):
        issue.text = format_teacher_issue_text(issue)
    elif isinstance(issue, UnplacedIssue):
        issue.text = format_unplaced_issue_text(issue)
    elif isinstance(issue, MissingRoomIssue):
        issue.text = format_missing_room_issue_text(issue)
    elif isinstance(issue, MissingInstructorIssue):
        issue.text = format_missing_instructor_issue_text(issue)
    elif isinstance(issue, InstructorIdIssue):
        issue.text = format_instructor_id_issue_text(issue)
    elif isinstance(issue, StudentEmailIssue):
        issue.text = format_student_email_issue_text(issue)
    elif isinstance(issue, UnbookedIssue):
        issue.text = format_unbooked_issue_text(issue)
    elif isinstance(issue, GroupIssue):
        issue.text = format_group_issue_text(issue)
    elif isinstance(issue, StudentIssue):
        issue.text = format_student_issue_text(issue)
    elif isinstance(issue, PerWeekIssue):
        issue.text = format_per_week_issue_text(issue)
    elif isinstance(issue, InstructorBannedSlotIssue):
        issue.text = format_instructor_banned_slot_issue_text(issue)
    elif isinstance(issue, InstructorPreferenceIssue):
        issue.text = format_instructor_preference_issue_text(issue)
    else:
        issue.text = format_outlook_issue_text(issue)
