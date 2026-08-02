import datetime as dtm
import re
from collections.abc import Generator

from pydantic import BaseModel

from ..utils import MOSCOW_TZ
from .config import Elective


def _parse_hhmm(value: str) -> dtm.time:
    hour_text, minute_text = value.split(":")
    return dtm.time(hour=int(hour_text), minute=int(minute_text))


class ElectiveEvent(BaseModel):
    elective: Elective
    "Elective object"
    start: dtm.datetime
    "Event start time"
    end: dtm.datetime
    "Event end time"
    location: str | None = None
    "Event location"
    class_type: str | None = None
    "Event type"
    group: str | None = None
    "Group to which the event belongs"
    spreadsheet_id: str
    "Spreadsheet ID"
    google_sheet_gid: str
    "Sheet GID"
    google_sheet_name: str
    "Sheet name from which this event was parsed"
    a1: str | None = None
    "A1 coordinates of the cell, may be a range"

    def __str__(self):
        return f"{self.elective.name} | {self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"


from .parser import ElectiveCell  # noqa: E402


def convert_cell_to_events(
    cell: ElectiveCell,
    date: dtm.date,
    timeslot: tuple[dtm.time, dtm.time],
    electives: list[Elective],
) -> Generator[ElectiveEvent]:
    """
    Parse cell value
    """
    overall_start, overall_end = timeslot
    overall_start = dtm.datetime.combine(date, overall_start, tzinfo=MOSCOW_TZ)
    overall_end = dtm.datetime.combine(date, overall_end, tzinfo=MOSCOW_TZ)

    for line in cell.value:
        yield parse_one_line_in_value(
            line,
            date,
            overall_start,
            overall_end,
            electives=electives,
            spreadsheet_id=cell.spreadsheet_id,
            google_sheet_gid=cell.google_sheet_gid,
            google_sheet_name=cell.google_sheet_name,
            a1=cell.a1,
        )


def parse_one_line_in_value(
    value: str,
    date: dtm.date,
    overall_start: dtm.datetime,
    overall_end: dtm.datetime,
    electives: list[Elective],
    *,
    spreadsheet_id: str,
    google_sheet_gid: str,
    google_sheet_name: str,
    a1: str | None = None,
) -> ElectiveEvent:
    """
    Process one line in cell value (was splitted by \\n before)

    - GAI (lec) online
    - PHL 101
    - PMBA (lab) (Group 1) 313
    - GDU 18:00-19:30 (lab) 101
    - OMML (18:10-19:50) 312
    - PGA 300
    - IQC (17:05-18:35) online
    - SMP online
    - ASEM (starts at 18:05) 101
    - AD STARTS AT 18:00 TILL 21:00
    - PM НАЧАЛО В 15:30 КОНЕЦ В 18:00 ОНЛАЙН
    """
    start = overall_start
    end = overall_end

    string = value.strip()

    # just first word as elective
    splitter = string.split(" ")
    elective_short_name = splitter[0]
    elective = next((elective for elective in electives if elective.short_name == elective_short_name), None)
    string = " ".join(splitter[1:])

    # find time xx:xx-xx:xx
    starts_at = ends_at = None
    if timeslot_m := re.search(r"\(?(\d{1,2}:\d{2})-(\d{1,2}:\d{2})\)?", string):
        starts_at = _parse_hhmm(timeslot_m.group(1))
        ends_at = _parse_hhmm(timeslot_m.group(2))
        string = string.replace(timeslot_m.group(0), "")

    # find starts at / STARTS AT / начало в
    if timeslot_m := re.search(
        r"\(?((?:starts?\s+at)|(?:начало\s+в))\s+(\d{1,2}:\d{2})\)?",
        string,
        flags=re.IGNORECASE,
    ):
        starts_at = _parse_hhmm(timeslot_m.group(2))
        string = string.replace(timeslot_m.group(0), "")

    # find ends at / TILL / конец в
    if timeslot_m := re.search(
        r"\(?((?:ends?\s+at)|(?:till)|(?:конец\s+в)|(?:до))\s+(\d{1,2}:\d{2})\)?",
        string,
        flags=re.IGNORECASE,
    ):
        ends_at = _parse_hhmm(timeslot_m.group(2))
        string = string.replace(timeslot_m.group(0), "")

    # find (lab), (lec)
    if class_type_m := re.search(r"\(?(lab|lec|лек|сем)\)?", string, flags=re.IGNORECASE):
        class_type = class_type_m.group(1).lower()
        string = string.replace(class_type_m.group(0), "")
    else:
        class_type = None

    # find (G1) / (Г1)
    if group_m := re.search(r"\(?((?:G|Г)\d+)\)?", string, flags=re.IGNORECASE):
        group = group_m.group(1).upper().replace("Г", "G")
        string = string.replace(group_m.group(0), "")
    else:
        group = None

    # find location (what is left)
    string = re.sub(r"\s+", " ", string).strip(" ,;/")
    if string:
        location = "ONLINE" if string.casefold() in {"online", "онлайн"} else string
    else:
        location = None

    if starts_at and not ends_at:
        duration = overall_end - overall_start
        start = dtm.datetime.combine(date, starts_at, tzinfo=MOSCOW_TZ)
        end = start + duration
    else:
        if starts_at:
            start = dtm.datetime.combine(date, starts_at, tzinfo=MOSCOW_TZ)
        if ends_at:
            end = dtm.datetime.combine(date, ends_at, tzinfo=MOSCOW_TZ)

    return ElectiveEvent(
        elective=elective or Elective(alias=elective_short_name.lower(), short_name=elective_short_name),
        location=location,
        class_type=class_type,
        group=group,
        start=start,
        end=end,
        spreadsheet_id=spreadsheet_id,
        google_sheet_gid=google_sheet_gid,
        google_sheet_name=google_sheet_name,
        a1=a1,
    )
