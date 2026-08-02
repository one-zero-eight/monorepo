import datetime as dtm
import re
from typing import Any
from zoneinfo import ZoneInfo

from src.schedule_assistant.modules.bookings.client import BookingDTO

MSK = ZoneInfo("Europe/Moscow")

_AUTO_PREFIXES = ("Schedule Assistant IU Auto:", "Auto:")
_RECURRENCE_DAY_RE = re.compile(r"<t:DaysOfWeek>([^<]+)</t:DaysOfWeek>")
_RECURRENCE_UNTIL_RE = re.compile(r"<t:EndDate>([^<]+)</t:EndDate>")
_SLOT_TITLE_RE = re.compile(r"^(.+?) \((\w+)")
_WEEKDAY_TO_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def booking_as_dict(booking: BookingDTO) -> dict[str, Any]:
    return {
        "room_id": booking.room_id,
        "title": booking.title,
        "start": booking.start_time.isoformat(),
        "end": booking.end_time.isoformat(),
        "categories": booking.categories,
        "recurrence": booking.recurrence,
    }


def _parse_dt(value: str) -> dtm.datetime:
    parsed = dtm.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=MSK)
    return parsed.astimezone(MSK)


def _strip_auto_title(title: str) -> str:
    text = title.strip()
    for prefix in _AUTO_PREFIXES:
        if text.casefold().startswith(prefix.casefold()):
            return text[len(prefix) :].strip()
    return text


def _categories_key(categories: Any) -> tuple[str, ...]:
    if not isinstance(categories, list):
        return ()
    return tuple(str(category) for category in categories if str(category) != "Auto")


def _recurrence_from_xml(recurrence: Any) -> dict[str, str] | None:
    if not isinstance(recurrence, str):
        return None
    day_match = _RECURRENCE_DAY_RE.search(recurrence)
    until_match = _RECURRENCE_UNTIL_RE.search(recurrence)
    if not day_match:
        return None
    return {
        "weekday": day_match.group(1).strip().lower(),
        "until_date": until_match.group(1).strip() if until_match else "",
    }


def _date_in_weekly_series(meeting_date: dtm.date, recurrence: dict[str, Any]) -> bool:
    weekday = str(recurrence.get("weekday", "")).strip().lower()
    start_date = dtm.date.fromisoformat(str(recurrence["start_date"]))
    until_date = dtm.date.fromisoformat(str(recurrence["until_date"]))
    return start_date <= meeting_date <= until_date and meeting_date.weekday() == _WEEKDAY_TO_INDEX[weekday]


def _times_match(booking: dict[str, Any], payload: dict[str, Any]) -> bool:
    booking_start = _parse_dt(str(booking["start"]))
    booking_end = _parse_dt(str(booking["end"]))
    payload_start = _parse_dt(str(payload["start"]))
    payload_end = _parse_dt(str(payload["end"]))

    if booking_start.time() != payload_start.time() or booking_end.time() != payload_end.time():
        return False

    payload_recurrence = payload.get("recurrence")
    if isinstance(payload_recurrence, dict):
        if not _date_in_weekly_series(booking_start.date(), payload_recurrence):
            return False
        booking_recurrence = _recurrence_from_xml(booking.get("recurrence"))
        if booking_recurrence is None:
            return True
        return booking_recurrence["weekday"] == str(
            payload_recurrence["weekday"]
        ).strip().lower() and booking_recurrence["until_date"] == str(payload_recurrence["until_date"])

    if _recurrence_from_xml(booking.get("recurrence")) is not None:
        return False

    return booking_start.date() == payload_start.date()


def _titles_match(payload_title: str, booking_title: str) -> bool:
    if payload_title == booking_title:
        return True
    if _strip_auto_title(booking_title) == payload_title:
        return True

    payload_match = _SLOT_TITLE_RE.match(payload_title)
    booking_match = _SLOT_TITLE_RE.match(_strip_auto_title(booking_title))
    if payload_match and booking_match:
        return (
            payload_match.group(1).strip() == booking_match.group(1).strip()
            and payload_match.group(2).strip() == booking_match.group(2).strip()
        )
    return False


def _identity_match(booking: dict[str, Any], payload: dict[str, Any]) -> bool:
    payload_title = str(payload.get("title") or "")
    booking_title = str(booking.get("title") or "")
    if _titles_match(payload_title, booking_title):
        return True

    payload_categories = _categories_key(payload.get("categories"))
    booking_categories = _categories_key(booking.get("categories"))
    return bool(payload_categories and payload_categories == booking_categories)


def booking_matches_payload(booking: dict[str, Any], payload: dict[str, Any]) -> bool:
    if str(booking.get("room_id")) != str(payload.get("room_id")):
        return False
    if not _times_match(booking, payload):
        return False
    return _identity_match(booking, payload)


def slot_has_matching_booking(
    payload: dict[str, Any],
    *,
    auto_bookings: list[dict[str, Any]],
    existing_bookings: list[dict[str, Any]],
) -> bool:
    return any(booking_matches_payload(booking, payload) for booking in [*auto_bookings, *existing_bookings])


def _iter_payload_occurrences(payload: dict[str, Any]) -> list[tuple[dtm.datetime, dtm.datetime]]:
    recurrence = payload.get("recurrence")
    if isinstance(recurrence, dict):
        weekday = str(recurrence["weekday"]).strip().lower()
        range_start = dtm.date.fromisoformat(str(recurrence["start_date"]))
        range_end = dtm.date.fromisoformat(str(recurrence["until_date"]))
        target = _WEEKDAY_TO_INDEX[weekday]
        start_time = _parse_dt(str(payload["start"])).time()
        end_time = _parse_dt(str(payload["end"])).time()
        occurrences: list[tuple[dtm.datetime, dtm.datetime]] = []
        current = range_start
        while current <= range_end:
            if current.weekday() == target:
                start = dtm.datetime.combine(current, start_time).replace(tzinfo=MSK)
                end = dtm.datetime.combine(current, end_time).replace(tzinfo=MSK)
                occurrences.append((start, end))
            current += dtm.timedelta(days=1)
        return occurrences

    start = _parse_dt(str(payload["start"]))
    end = _parse_dt(str(payload["end"]))
    return [(start, end)]


def detect_payload_conflicts(
    payload: dict[str, Any],
    existing_bookings: list[BookingDTO],
) -> list[tuple[dtm.datetime, dtm.datetime, list[BookingDTO]]]:
    room_id = payload.get("room_id")
    if not room_id:
        return []

    hits: list[tuple[dtm.datetime, dtm.datetime, list[BookingDTO]]] = []
    booking_dicts = [booking_as_dict(booking) for booking in existing_bookings]

    for occurrence_start, occurrence_end in _iter_payload_occurrences(payload):
        conflicts: list[BookingDTO] = []
        for booking, booking_dict in zip(existing_bookings, booking_dicts, strict=True):
            if str(booking.room_id) != str(room_id):
                continue
            if not (occurrence_start < booking.end_time and booking.start_time < occurrence_end):
                continue
            if booking_matches_payload(booking_dict, payload):
                continue
            conflicts.append(booking)
        if conflicts:
            hits.append((occurrence_start, occurrence_end, conflicts))

    return hits
