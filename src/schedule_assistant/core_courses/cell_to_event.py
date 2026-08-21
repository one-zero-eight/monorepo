"""
This file should be synced between:
https://github.com/one-zero-eight/parsers/blob/main/src/core_courses/cell_to_event.py
https://github.com/one-zero-eight/schedule-builder-backend/blob/main/src/core_courses/cell_to_event.py
"""

import datetime as dtm
import re
import warnings
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.logging_ import logger

from ..utils import MOSCOW_TZ, WEEKDAYS, remove_repeating_spaces_and_trailing_spaces
from .config import Target, override_matches_row
from .location_parser import Item, extract_room_from_location_string, parse_location_string
from .parser import CoreCourseCell


class CoreCourseEvent(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    course: str
    "Academic course"
    group: str
    "Academic group"
    group_student_number: int | None = None
    "Academic group student number"

    start_time: dtm.time
    "Event start time"
    end_time: dtm.time
    "Event end time"
    weekday: int = Field(..., ge=0, le=6)
    "Event weekday"

    starts: dtm.date
    "Event start date"
    ends: dtm.date
    "Event end date"
    dtstamp: dtm.datetime
    "Event timestamp"

    original_value: list[str | None]
    "Original cell values"
    spreadsheet_id: str
    "Spreadsheet ID"
    google_sheet_gid: str
    "Sheet GID"
    google_sheet_name: str
    "Sheet name"
    a1: str | None = None
    "A1 coordinates of left-upper cell, may be a range"

    subject: str
    "Event subject"
    teacher: str | None = None
    "Event teacher"
    location: str | None = Field(default=None)
    "Event location (lower priority with respect to location_item)"
    location_item: Item | None = None
    "Parsed location item from location string"
    dont_care_location_string: bool = Field(default=False, exclude=True)
    "Keep room only from location string; ignore date/time modifiers"
    class_type: Literal["lec", "tut", "lab", "лек", "тут", "лаб"] | None = None
    "Event class type"

    def __init__(self, **data):
        super().__init__(**data)
        self.process_subject()
        self.process_teacher()
        self.process_location()

    def process_subject(self):
        """Process subject string

        - "Mathematical Analysis I (lec)" -> "Mathematical Analysis I" + lec as type
        - "Philosophy II (Introduction to AI) (lec)" -> "Philosophy II: Introduction to AI" + lec as type
        - "Analytical Geometry and Linear Algebra I" -> "Analytical Geometry and Linear Algebra I"
        """

        subject = self.subject
        matches = re.finditer(r"\((.+?)\)", subject)
        for match in matches:
            inside_brackets = match.group(1)

            if re.match(r"^(?:lec|tut|lab|тут|лек|лаб)$", inside_brackets, flags=re.IGNORECASE):
                # if inside_brackets is "lec" or "tut" or "lab" then it is class type
                subject = subject.replace(match[0], "", 1)
                self.class_type = inside_brackets.lower()  # type: ignore
            else:
                # if inside_brackets is not "lec" or "tut" or "lab" then it is part of subject
                subject = subject.replace(match[0], f": {inside_brackets.strip()}", 1)

        # remove whitespaces before colons(:)
        subject = re.sub(r"\s*:\s*", ": ", subject)
        subject = remove_repeating_spaces_and_trailing_spaces(subject)
        self.subject = subject

    def process_teacher(self):
        """Process teacher string

        - "Ivan Ivanov" -> "Ivan Ivanov"
        - "Maria Razmazina/David Orok" -> "Maria Razmazina, David Orok"
        - "Georgiy Gelvanovsky,Rabab Marouf, Ruslan Saduov, Oksana Zhirosh"
          -> "Georgiy Gelvanovsky, Rabab Marouf, Ruslan Saduov, Oksana Zhirosh"
        - "M. Reza Bahrami" -> "M. Reza Bahrami"
        """
        if self.teacher is None:
            return

        teacher = self.teacher
        # remove spaces before and after commas(,) and slashes(/) and replace them with comma(,)
        teacher = re.sub(r"\s*[,/]\s*", ",", teacher)
        # remove multiple commas in a row
        teacher = re.sub(r"(,\s*)+,", ",", teacher)
        # remove trailing commas
        teacher = re.sub(r"\s*,\s*$", "", teacher)
        # remove trailing spaces
        teacher = teacher.strip()
        self.teacher = teacher

    def process_location(self):
        """
        Process location string, See corresponding tests in tests/test_location_strings.py
        """
        if self.location is None:
            return
        location = self.location
        # Upper case location
        location = location.upper()
        # replace " and " with comma
        location = re.sub(r"\s+AND\s+", ", ", location)
        self.location = location

        if not re.match(r"ELECTIVE COURSES? ON PHYSICAL EDUCATION", location):  # no need to parse this location
            if self.dont_care_location_string:
                self.location = extract_room_from_location_string(location)
                self.location_item = None
                if self.location is None:
                    warnings.warn(f"Location `{location}` is not parsed properly")
                return

            self.location_item = parse_location_string(location)

            if self.location_item is None:
                warnings.warn(f"Location `{location}` is not parsed properly")

    def __str__(self):
        timeslot = f"{self.start_time.strftime('%H:%M')}-{self.start_time.strftime('%H:%M')}"
        return f"{self.course} / {self.group} | {self.subject} {timeslot}"


def convert_cell_to_event(
    cell: CoreCourseCell,
    weekday: str,
    timeslot: tuple[dtm.time, dtm.time],
    course: str,
    group: str,
    target: Target,
    *,
    dont_care_location_string: bool = False,
) -> CoreCourseEvent | None:
    """
    Convert cell to event
    """
    weekday_int = WEEKDAYS.index(weekday)
    start_time, end_time = timeslot

    try:
        subject = teacher = location = None

        match cell.value:
            case None, subject, None:
                pass
            case subject, teacher, location:
                pass
            case _:
                raise ValueError(f"Unknown value: {cell.value}")

        starts = target.start_date
        ends = target.end_date

        def preprocess_group(value: str) -> tuple[str, int | None]:
            """
            Process group name

            - "M21-DS(16)" -> "M21-DS"
            - "M22-TE-01 (10)" -> "M22-TE-01"
            - "B20-SD-02 (29)" -> "B20-SD-02"
            """
            student_number = None
            # Match (G\d+) or (\d+) at the end
            if student_number_m := re.search(r"\(?(G\d+|\d+)\)?\s*$", value):
                match_text = student_number_m.group(1)
                if match_text.startswith("G"):
                    student_number = int(match_text[1:])
                else:
                    student_number = int(match_text)
                value = value.replace(student_number_m.group(0), "").strip()
            return value, student_number

        group, group_student_number = preprocess_group(group)

        sheet_name = cell.google_sheet_name or target.sheet_name
        for override in target.override:
            if override_matches_row(override, group=group, course=course, sheet_name=sheet_name):
                starts = override.start_date
                ends = override.end_date
                break

        event = CoreCourseEvent(
            start_time=start_time,
            end_time=end_time,
            dtstamp=dtm.datetime.combine(target.start_date, dtm.time.min, tzinfo=MOSCOW_TZ),
            starts=starts,
            ends=ends,
            weekday=weekday_int,
            course=course,
            group=group,
            group_student_number=group_student_number,
            original_value=cell.value,
            spreadsheet_id=cell.spreadsheet_id,
            google_sheet_gid=cell.google_sheet_gid,
            google_sheet_name=cell.google_sheet_name,
            a1=cell.a1,
            subject=subject,
            teacher=teacher,
            location=location,
            dont_care_location_string=dont_care_location_string,
        )
        return event
    except ValueError:
        logger.error(f"Error parsing cell {cell.value!r} for {course} {group} {weekday} {timeslot}", exc_info=True)
        return None
