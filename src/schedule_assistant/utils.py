"""
This file should be synced between:
https://github.com/one-zero-eight/parsers/blob/main/src/utils.py
https://github.com/one-zero-eight/schedule-builder-backend/blob/main/src/parsers/utils.py
"""

__all__ = [
    "TIMEZONE",
    "WEEKDAYS",
    "WEEKDAYS",
    "nearest_weekday",
    "prettify_string",
    # "get_color",
    # "get_base_calendar",
    "remove_repeating_spaces_and_trailing_spaces",
    "set_one_space_after_comma_and_remove_repeating_commas",
    "set_one_space_around_brackets_and_remove_repeating_brackets",
    "sluggify",
]

import datetime as dtm
import io
import re
from enum import StrEnum

import httpx

from src.schedule_assistant.weekday import WEEKDAYS, weekday_index

TIMEZONE = "Europe/Moscow"
MOSCOW_TZ = dtm.timezone(dtm.timedelta(hours=3), name="Europe/Moscow")


async def fetch_xlsx_spreadsheet(spreadsheet_id: str) -> io.BytesIO:
    """
    Export xlsx file from Google Sheets and return it as BytesIO object.

    :param spreadsheet_id: id of Google Sheets spreadsheet
    :return: xlsx file as BytesIO object
    """

    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
    export_url = spreadsheet_url + "/export?format=xlsx"

    async with httpx.AsyncClient() as client:
        response = await client.get(export_url, follow_redirects=True)
        response.raise_for_status()
        return io.BytesIO(response.content)


async def get_sheet_gids(spreadsheet_id: str) -> dict[str, str]:
    """
    Get sheet name -> gid mapping from Google Spreadsheet HTML view.

    :param spreadsheet_id: id of Google Sheets spreadsheet
    :return: mapping of sheet name to gid
    """
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/htmlview"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        html = response.text

        sheet_mappings = {}
        # Pattern: items.push({name: "...", gid: "..."}) structure
        pattern_items = r'items\.push\(\{name:\s*"([^"]+)",\s*[^}]*gid:\s*"(\d+)"'
        items_matches = re.findall(pattern_items, html)
        for name, gid in items_matches:
            # Unescape JavaScript string escapes
            name_clean = name.replace("\\/", "/").replace('\\"', '"')
            sheet_mappings[name_clean] = gid

        return sheet_mappings


def nearest_weekday(date: dtm.date, day: int | str) -> dtm.date:
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
        normalized = day.upper().strip()
        if normalized in WEEKDAYS:
            day = weekday_index(normalized)
        else:
            day = ["mo", "tu", "we", "th", "fr", "sa", "su"].index(day[:2].lower())

    days = (day - date.weekday() + 7) % 7
    return date + dtm.timedelta(days=days)


def sanitize_sheet_name(name: str) -> str:
    r"""Convert any string to a valid Excel sheet name following Google Sheets export behavior.

    Excel sheet name restrictions:
    - Max 31 characters
    - Cannot contain: / \ ? * [ ] :
    - Cannot start/end with single quotes
    """
    if not name or not name.strip():
        return "Sheet1"

    name = name.strip()
    name = re.sub(r"[/\\?*\[\]:]", "", name)
    name = name.strip("'")

    if len(name) > 31:
        name = name[:31].rstrip()

    if not name or name.isspace():
        return "Sheet1"

    return name


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
    s = re.sub(r"[^a-z0-9а-яА-ЯёЁ\s-]", " ", s)
    s = re.sub(r"\s+", "-", s)
    # remove multiple dashes
    s = re.sub(r"-{2,}", "-", s)
    # remove leading and trailing dashes
    s = s.strip("-")
    return s


class CSS3Color(StrEnum):
    BROWN = "brown"
    CADETBLUE = "cadetblue"
    CHOCOLATE = "chocolate"
    DARK_CYAN = "darkcyan"
    DARK_GREEN = "darkgreen"
    DARK_MAGENTA = "darkmagenta"
    DARK_OLIVE_GREEN = "darkolivegreen"
    DARK_RED = "darkred"
    DARK_SLATE_BLUE = "darkslateblue"
    DARK_SLATE_GRAY = "darkslategray"
    DIM_GRAY = "dimgray"
    FIREBRICK = "firebrick"
    FOREST_GREEN = "forestgreen"
    GRAY = "gray"
    INDIAN_RED = "indianred"
    LIGHT_SLATE_GRAY = "lightslategray"
    MAROON = "maroon"
    MEDIUM_VIOLET_RED = "mediumvioletred"
    MIDNIGHT_BLUE = "midnightblue"
    INDIGO = "indigo"
    REBECCA_PURPLE = "rebeccapurple"
    SEA_GREEN = "seagreen"
    TEAL = "teal"

    @classmethod
    def get_by_index(cls, idx: int):
        return list(cls.__members__.values())[idx]


# We dont have icalendar in this project, so we don't need to implement this
# def get_color(text_to_hash: str) -> icalendar.vText:
#     # Use SHA256 for better distribution and fewer collisions
#     hash_bytes = hashlib.sha256(text_to_hash.encode("utf-8")).digest()
#     # Convert first 4 bytes to integer for better distribution
#     h = int.from_bytes(hash_bytes[:4], byteorder="big") % len(CSS3Color.__members__)
#     return icalendar.vText(CSS3Color.get_by_index(h))


# def get_base_calendar() -> icalendar.Calendar:
#     """
#     Get base calendar with default properties (version, prodid, etc.)
#     :return: base calendar
#     :rtype: icalendar.Calendar
#     """

#     calendar = icalendar.Calendar(
#         prodid="-//one-zero-eight//InNoHassle Schedule",
#         version="2.0",
#         method="PUBLISH",
#     )

#     calendar["x-wr-caldesc"] = "Generated by InNoHassle Schedule"
#     calendar["x-wr-timezone"] = TIMEZONE

#     # add timezone
#     timezone = icalendar.Timezone(tzid=TIMEZONE)
#     timezone["x-lic-location"] = TIMEZONE
#     # add standard timezone
#     standard = icalendar.TimezoneStandard()
#     standard.add("tzoffsetfrom", datetime.timedelta(hours=3))
#     standard.add("tzoffsetto", datetime.timedelta(hours=3))
#     standard.add("tzname", "MSK")
#     standard.add("dtstart", datetime.datetime(1970, 1, 1))
#     timezone.add_component(standard)
#     calendar.add_component(timezone)

#     return calendar


def remove_repeating_spaces_and_trailing_spaces(s: str) -> str:
    return re.sub(r"\s{2,}", " ", s).strip()


def set_one_space_around_brackets_and_remove_repeating_brackets(s: str) -> str:
    """
    Prettify string with brackets.

    :param s: string to prettify
    :type s: str
    :return: prettified string
    :rtype: str
    """
    # remove multiple brackets in a row
    s = re.sub(r"(\(\s*)+\(", "(", s)
    s = re.sub(r"(\)\s*)+\)", ")", s)

    # set only one space after and before brackets except for brackets in the end of string
    s = re.sub(r"\s*\([ \t]*", " (", s)
    s = re.sub(r"\s*\)[ \t]+", ") ", s)
    s = s.strip()
    return s


def set_one_space_after_comma_and_remove_repeating_commas(s: str) -> str:
    """
    Prettify string with commas.

    :param s: string to prettify
    :type s: str
    :return: prettified string
    :rtype: str
    """
    # remove multiple commas in a row
    s = re.sub(r"(\,\s*)+\,", ",", s)
    # set only one space after and before commas except for commas in the end of string
    s = re.sub(r"\s*\,\s*", ", ", s)
    s = s.strip()
    return s


def prettify_string(string: str | None) -> str | None:
    """
    Set only one whitespace before "(" and after ")". Remove repeating brackets.
    Set only one whitespace after ",". Remove repeating commas.
    Remove repeating spaces and trailing spaces. Strip string.

    :param string: string to beautify
    :type string: str
    :return: beautified string
    :rtype: str
    """
    if isinstance(string, str):
        # set only one space between brackets and remove repeating brackets
        string = set_one_space_around_brackets_and_remove_repeating_brackets(string)
        # set only one space after commas and remove repeating commas
        string = set_one_space_after_comma_and_remove_repeating_commas(string)
        # remove repeating spaces and trailing spaces
        string = remove_repeating_spaces_and_trailing_spaces(string)
    return string
