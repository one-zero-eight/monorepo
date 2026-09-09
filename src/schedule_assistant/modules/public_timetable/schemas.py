"""Public timetable whitelist, deliberately independent of editor/config models."""

import datetime as dtm
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.schedule_assistant.weekday import Weekday


class PublicTimetableModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_attribute_docstrings=True)


class PublicDateRange(PublicTimetableModel):
    start_date: dtm.date
    end_date: dtm.date


class PublicTimeSlot(PublicTimetableModel):
    start_time: dtm.time
    end_time: dtm.time


class PublicTrack(PublicTimetableModel):
    code: str
    name: str
    groups: list[str] = Field(default_factory=list)


class PublicProgram(PublicTimetableModel):
    code: str
    name: str
    tracks: list[PublicTrack] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    time_slots: list[PublicTimeSlot] | None = None
    semester: PublicDateRange | None = None


class PublicSection(PublicTimetableModel):
    code: str
    name: str
    default_layout: Literal["groups", "compact_groups", "calendar"] | None = None
    programs: list[PublicProgram] = Field(default_factory=list)


class PublicTerm(PublicTimetableModel):
    name: str
    semester: PublicDateRange
    days: list[Weekday]
    starting_day: Weekday
    time_slots: list[PublicTimeSlot]
    sections: list[PublicSection] = Field(default_factory=list)


class PublicRoom(PublicTimetableModel):
    id: str
    name: str
    capacity: int | None = None


class PublicInstructor(PublicTimetableModel):
    id: str
    name_en: str | None = None
    name_ru: str | None = None
    email: str | None = None
    alias: str | None = None
    position: str | None = None


class PublicStudentGroup(PublicTimetableModel):
    code: str
    name: str | None = None


class PublicWeeklyAlternation(PublicTimetableModel):
    anchor_week: dtm.date


class PublicWeeklyPatternSlotEdit(PublicTimetableModel):
    select_week: dtm.date
    cancel: bool = False
    date: dtm.date | None = None
    start_time: dtm.time | None = None
    end_time: dtm.time | None = None
    room: str | None = None
    instructor: str | list[str] | None = None
    notes: str | None = None
    "Null inherits series notes; an empty string suppresses them."


class PublicWeeklyPatternSlot(PublicTimetableModel):
    weekday: Weekday
    start_time: dtm.time
    end_time: dtm.time
    room: str | None = None
    instructor: str | list[str] | None = None
    alternation: PublicWeeklyAlternation | None = None
    edits: list[PublicWeeklyPatternSlotEdit] | None = None


class PublicSessionOccurrence(PublicTimetableModel):
    date: dtm.date
    start_time: dtm.time
    end_time: dtm.time
    room: str | None = None
    instructor: str | list[str] | None = None
    notes: str | None = None
    "Null inherits series notes; an empty string suppresses them."


class PublicComponentSessionSeries(PublicTimetableModel):
    audience: list[str] = Field(default_factory=list)
    weekly_pattern: list[PublicWeeklyPatternSlot] | None = None
    dates_pattern: list[PublicSessionOccurrence] | None = None
    notes: str = ""
    "Public notes inherited by occurrences without their own override."


class PublicComponent(PublicTimetableModel):
    tag: str
    audience: list[str] = Field(default_factory=list)
    sessions: list[PublicComponentSessionSeries] | None = None


class PublicCourseInstructor(PublicTimetableModel):
    id: str
    role: str


class PublicCourse(PublicTimetableModel):
    name: str
    color: str | None = None
    section_code: str
    short_name: str | None = None
    name_ru: str | None = None
    short_name_ru: str | None = None
    instructors: list[PublicCourseInstructor] = Field(default_factory=list)
    components: list[PublicComponent]


class PublicTimetable(PublicTimetableModel):
    term: PublicTerm
    rooms: list[PublicRoom] = Field(default_factory=list)
    instructors: list[PublicInstructor] = Field(default_factory=list)
    students_groups: list[PublicStudentGroup] = Field(default_factory=list)
    courses: list[PublicCourse] = Field(default_factory=list)
