"""
This file should be synced between:
https://github.com/one-zero-eight/parsers/blob/main/src/core_courses/config.py
https://github.com/one-zero-eight/schedule-builder-backend/blob/main/src/core_courses/config.py
"""

import datetime as dtm

from pydantic import BaseModel


class Override(BaseModel):
    groups: list[str]
    "Groups"
    courses: list[str]
    "Courses"
    start_date: dtm.datetime
    "Datetime start"
    end_date: dtm.date
    "Datetime end"


class Target(BaseModel):
    sheet_name: str
    "Sheet name"
    start_date: dtm.date
    "Datetime start"
    end_date: dtm.date
    "Datetime end"
    override: list[Override]
    "Override"


class Tag(BaseModel):
    alias: str
    "Slugged alias of tag"
    type: str
    "Type"
    name: str
    "Short name"


class CoreCoursesConfig(BaseModel):
    targets: list[Target]
    "List of targets"
    semester_tag: Tag
    "Semester tag"
    spreadsheet_id: str
    "Spreadsheet ID"
    ignored_subjects: list[str] = [
        "Elective courses on Physical Education",
        "Elective course on Physical Education",
    ]
    dont_care_location_string: bool = False
    "Parse location strings for room only; ignore ONLY ON, WEEK, EXCEPT, etc."
