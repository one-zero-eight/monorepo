"""
This file should be synced between:
https://github.com/one-zero-eight/parsers/blob/main/src/core_courses/config.py
https://github.com/one-zero-eight/schedule-builder-backend/blob/main/src/core_courses/config.py
"""

import datetime as dtm

from pydantic import BaseModel, field_validator

# Spreadsheet cohort header → ScheduleConfig program base (without _EN/_RU).
_COHORT_TO_PROGRAM_BASE: dict[str, str] = {
    "BS - Year 1": "BS_Y1",
    "BS - Year 2": "BS_Y2",
    "BS - Year 3": "BS_Y3",
    "MS - Year 1": "MS_Y1",
    "PhD - Year 1": "PHD_Y1",
}

_RU_SHEET_MARKERS = ("ru program", "ru programs")


def sheet_language(sheet_name: str) -> str | None:
    """Return 'RU' for Russian-track sheets, 'EN' for English-track sheets, else None."""
    lowered = sheet_name.strip().casefold()
    if any(marker in lowered for marker in _RU_SHEET_MARKERS):
        return "RU"
    if lowered:
        return "EN"
    return None


def program_codes_for_row(*, course: str, sheet_name: str) -> set[str]:
    """Program codes implied by a spreadsheet row (cohort header + sheet language)."""
    base = _COHORT_TO_PROGRAM_BASE.get(course.strip())
    if base is None:
        return set()
    codes = {base}
    if not base.startswith("BS_"):
        return codes
    language = sheet_language(sheet_name)
    if language == "EN":
        codes.add(f"{base}_EN")
    elif language == "RU":
        codes.add(f"{base}_RU")
    else:
        codes.add(f"{base}_EN")
        codes.add(f"{base}_RU")
    return codes


def override_matches_row(
    override: Override,
    *,
    group: str,
    course: str,
    sheet_name: str,
) -> bool:
    if group in override.groups or course in override.courses:
        return True
    if not override.programs:
        return False
    row_codes = program_codes_for_row(course=course, sheet_name=sheet_name)
    return any(code.strip() in row_codes for code in override.programs if code.strip())


class Override(BaseModel):
    groups: list[str] = []
    "Groups"
    courses: list[str] = []
    "Courses"
    programs: list[str] = []
    "ScheduleConfig-style program codes (e.g. BS_Y1_EN); matched via cohort + sheet"
    start_date: dtm.date
    "Inclusive teaching window start"
    end_date: dtm.date
    "Inclusive teaching window end"

    @field_validator("start_date", mode="before")
    @classmethod
    def _coerce_start_date(cls, value: object) -> object:
        if isinstance(value, dtm.datetime):
            return value.date()
        return value


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
