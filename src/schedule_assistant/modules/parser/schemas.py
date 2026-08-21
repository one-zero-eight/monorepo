import datetime as dtm
from typing import Literal, Self

from pydantic import Field, model_validator

from src.schedule_assistant.core_courses.location_parser import Item
from src.schedule_assistant.schema_base import ScheduleAssistantSchema


class ElectiveLessonOccurrence(ScheduleAssistantSchema):
    start_time: dtm.time
    "Start time of lesson"
    end_time: dtm.time
    "End time of lesson"
    date: dtm.date
    "Specific date of the lesson"
    room: str | tuple[str, ...] | None = None
    "Room for this occurrence; may differ from other occurrences"
    a1_range: str | None = None
    "Spreadsheet cell for this date"

    @model_validator(mode="after")
    def validate_time(self) -> Self:
        if not self.start_time < self.end_time:
            raise ValueError("Start time has to be less than end time")
        return self


class CoreCourseComponent(ScheduleAssistantSchema):
    type: Literal["lec", "tut", "lab", "лек", "тут", "лаб"] | str | None = None
    "Type of the lesson component"
    weekday: str | None = None
    "Weekday of a lesson"
    start_time: dtm.time
    "Start time of lesson"
    end_time: dtm.time
    "End time of lesson"
    room: str | tuple[str, ...] | None = None
    "Room for lesson"
    instructor: str | None = None
    "Instructor on lesson"
    audience: list[str] = Field(default_factory=list)
    "Student groups for this component"
    students_number: int | None = None
    "Number of students in the group"
    modifiers: Item | None = None
    "Parsed location string modifiers"
    a1_range: str | None = None
    "Range of the lesson in the spreadsheet"

    @model_validator(mode="after")
    def validate_time(self) -> Self:
        if not self.start_time < self.end_time:
            raise ValueError("Start time has to be less than end time")
        return self


class GroupedCoreCourse(ScheduleAssistantSchema):
    cohort: str | None = None
    "Academic cohort (course row in spreadsheet)"
    subject: str
    "Subject name"
    spreadsheet_id: str
    google_sheet_gid: str
    google_sheet_name: str
    start_date: dtm.date | None = None
    "Term start date for this sheet"
    end_date: dtm.date | None = None
    "Term end date for this sheet"
    components: list[CoreCourseComponent]
    "Schedule components (lec/lab/tut slots)"


class GroupedElective(ScheduleAssistantSchema):
    subject: str
    "Elective title"
    alias: str | None = None
    "Elective short alias from spreadsheet (for example, ICD)"
    instructor: str | None = None
    spreadsheet_id: str
    google_sheet_gid: str
    google_sheet_name: str
    audience: list[str] = Field(default_factory=list)
    "Elective alias and/or parallel stream groups"
    occurrences: list[ElectiveLessonOccurrence]
    "One entry per concrete date/time slot"


class Lesson(ScheduleAssistantSchema):
    # > Main lesson info
    lesson_name: str
    "Name of the lesson"
    lesson_class_type: Literal["lec", "tut", "lab", "лек", "тут", "лаб"] | str | None = None
    "Type of the lesson"
    source_type: Literal["core_course", "elective"] | None = None
    "Whether the lesson comes from core courses or electives"
    weekday: str | None = None
    "Weekday of a lesson"
    start_time: dtm.time
    "Start time of lesson"
    end_time: dtm.time
    "End time of lesson"
    room: str | tuple[str, ...] | None = None
    "Room for lesson, None - TBA, if list - multiple rooms simultaneously"
    teacher: str | None = None
    "Teacher on lesson"
    # <

    # > Course and group info
    course_name: str | None = None
    "Name of the course"
    group_name: str | tuple[str, ...] | None = None
    "Name of the group or list of groups"
    students_number: int | None = None
    "Number of students in the group"
    # <

    # > Location Parser extras
    date_on: list[dtm.date] | None = None
    "Specific dates with lessons"
    date_except: list[dtm.date] | None = None
    "Specific dates when there is no lessons"
    date_from: dtm.date | None = None
    "Date from which the lesson starts"
    window_start: dtm.date | None = None
    "Resolved teaching window start (target/override)"
    window_end: dtm.date | None = None
    "Resolved teaching window end (target/override)"
    modifiers: Item | None = None
    "Parsed location string modifiers (internal, used when grouping)"
    # <

    # > Google Spreadsheet info
    spreadsheet_id: str
    "Spreadsheet ID"
    google_sheet_gid: str
    "Google Spreadsheet ID of the sheet"
    google_sheet_name: str
    "Sheet name to which the lesson belongs in Google Spreadsheet"
    a1_range: str | None = None
    "Range of the lesson: may be multiple cells, for example 'A1:A10'"
    # <

    @model_validator(mode="after")
    def validate_date(self) -> Self:
        if not self.start_time < self.end_time:
            raise ValueError("Start time has to be less than end time")
        return self
