__all__ = [
    "TIMEZONE",
    "aware_utcnow",
    "get_color",
    "get_current_year",
    "get_weekday_rrule",
    "locate_ics_by_path",
    "nearest_weekday",
    "sluggify",
    "validate_calendar",
    "validate_vevent",
]

import datetime
import re
from pathlib import Path, PurePath
from zlib import crc32

import dateutil.rrule
import icalendar

from src.schedule.config import settings

TIMEZONE = "Europe/Moscow"


def nearest_weekday(date: datetime.date, day: int | str) -> datetime.date:
    """
    Returns the date of the next given weekday after
    the given date. For example, the date of next Monday.

    :param date: date to start from
    :type date: datetime.date
    :param day: weekday to find (0 is Monday, 6 is Sunday)
    :type day: int
    :return: date of the next given weekday
    :rtype: datetime.date
    """
    if isinstance(day, str):
        day = ["mo", "tu", "we", "th", "fr", "sa", "su"].index(day[:2].lower())

    days = (day - date.weekday() + 7) % 7
    return date + datetime.timedelta(days=days)


def get_current_year() -> int:
    """Returns current year."""
    return datetime.datetime.now().year


def get_weekday_rrule(end_date: datetime.date) -> dict:
    """
    Get RRULE for recurrence with weekly interval and end date.

    :param end_date: end date
    :type end_date: datetime.date
    :return: RRULE dictionary with weekly interval and end date.
        See `here <https://icalendar.org/iCalendar-RFC-5545/3-8-5-3-recurrence-rule.html>`__
    :rtype: dict
    """
    return {"FREQ": "WEEKLY", "INTERVAL": 1, "UNTIL": end_date}


css3colors = list(
    {
        "brown",
        "cadetblue",
        "chocolate",
        "darkcyan",
        "darkgreen",
        "darkmagenta",
        "darkolivegreen",
        "darkred",
        "darkslateblue",
        "darkslategray",
        "dimgray",
        "firebrick",
        "forestgreen",
        "gray",
        "indianred",
        "lightslategray",
        "maroon",
        "mediumvioletred",
        "midnightblue",
        "indigo",
        "rebeccapurple",
        "seagreen",
        "teal",
    }
)


def get_color(to_hash: str):
    hash_ = crc32(to_hash.encode("utf-8"))
    return css3colors[hash_ % len(css3colors)]


def sluggify(s: str) -> str:
    """
    Sluggify string.

    :param s: string to sluggify
    :type s: str
    :return: sluggified string
    :rtype: str
    """
    s = s.lower()
    # also translates special symbols, brackets, commas, etc.
    s = re.sub(r"[^a-z0-9а-я\s-]", " ", s)
    s = re.sub(r"\s+", "-", s)
    # remove multiple dashes
    s = re.sub(r"-{2,}", "-", s)

    return s


def validate_calendar(calendar: icalendar.Calendar):
    for event in calendar.walk("VEVENT"):
        event: icalendar.Event
        validate_vevent(event)


def validate_vevent(event: icalendar.Event):
    if "UID" not in event:
        raise ValueError("Event has no UID", event)
    #
    # if "DTSTAMP" not in event:
    #     raise ValueError("Event has no DTSTAMP", event)

    vddd_dtstart: icalendar.vDDDTypes | None = event.get("DTSTART")
    vddd_dtend: icalendar.vDDDTypes | None = event.get("DTEND")
    vddd_duration: icalendar.vDDDTypes | None = event.get("DURATION")

    if not vddd_dtstart:
        raise ValueError("Event has no DTSTART", event)

    if not vddd_dtend and not vddd_duration and vddd_dtstart.params.get("VALUE") != "DATE":
        raise ValueError("Event has no DTEND or DURATION", event)

    if vddd_dtend and vddd_duration:
        raise ValueError("Event has both DTEND and DURATION", event)

    if vddd_dtend and vddd_dtstart.dt > vddd_dtend.dt:
        raise ValueError("DTSTART is later than DTEND", event)

    if "RRULE" in event:
        # should be compatible with dtstart
        rrule: dateutil.rrule.rrule = dateutil.rrule.rrulestr(
            event["RRULE"].to_ical().decode(), dtstart=vddd_dtstart.dt
        )
        rrule_dates = rrule.__iter__()
        rrule_first_dt = next(rrule_dates, None)

        if rrule_first_dt:
            rrule_first_date = rrule_first_dt.date()

            if isinstance(vddd_dtstart.dt, datetime.datetime):
                vdd_date = vddd_dtstart.dt.date()
            elif isinstance(vddd_dtstart.dt, datetime.date):
                vdd_date = vddd_dtstart.dt
            else:
                raise ValueError("DTSTART is not datetime or date", event)

            if rrule_first_date != vdd_date:
                raise ValueError("DTSTART is not compatible with RRULE", event)
        else:
            raise ValueError("RRULE produces empty list", event)


def aware_utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def locate_ics_by_path(path: str) -> Path:
    normalized_path = PurePath(path)
    if normalized_path.is_absolute() or ".." in normalized_path.parts:
        raise ValueError(f"Path escapes predefined ICS directory: {path!r}")
    if normalized_path.name == "" or normalized_path.suffix != ".ics":
        raise ValueError(f"Path must point to an .ics file inside predefined/ics: {path!r}")

    base_dir = (settings.predefined_dir / "ics").resolve(strict=False)
    ics_path = (base_dir / normalized_path).resolve(strict=False)

    if not ics_path.is_relative_to(base_dir):
        raise ValueError(f"Path escapes predefined ICS directory: {path!r}")
    if ics_path.exists() and ics_path.is_dir():
        raise ValueError(f"Path must point to a file, not a directory: {path!r}")

    return ics_path


def get_base_calendar() -> icalendar.Calendar:
    """
    Get base calendar with default properties (version, prodid, etc.)
    :return: base calendar
    :rtype: icalendar.Calendar
    """

    calendar = icalendar.Calendar(
        prodid="-//one-zero-eight//InNoHassle Schedule",
        version="2.0",
        method="PUBLISH",
    )

    calendar["x-wr-caldesc"] = "Generated by InNoHassle Schedule"
    calendar["x-wr-timezone"] = TIMEZONE
    #
    # add timezone
    timezone = icalendar.Timezone(tzid=TIMEZONE)
    timezone["x-lic-location"] = TIMEZONE
    # add standard timezone
    standard = icalendar.TimezoneStandard()
    standard.add("tzoffsetfrom", datetime.timedelta(hours=3))
    standard.add("tzoffsetto", datetime.timedelta(hours=3))
    standard.add("tzname", "MSK")
    standard.add("dtstart", datetime.datetime(1970, 1, 1))
    timezone.add_component(standard)
    calendar.add_component(timezone)

    return calendar
