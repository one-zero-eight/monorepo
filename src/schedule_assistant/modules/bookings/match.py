import datetime as dtm
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

MSK = ZoneInfo("Europe/Moscow")

_AUTO_TITLE_PREFIXES = (
    "Schedule Assistant IU Auto:",
    "Auto:",
)
_BOOKING_TITLE_FORWARD_PREFIXES = ("FW:", "RE:", "Fwd:")
_SCHEDULE_ASSISTANT_IU_TITLE_RE = re.compile(
    r"^Schedule Assistant IU (?:Auto:\s*)?",
    re.IGNORECASE,
)
_SLOT_TITLE_RE = re.compile(r"^(.+?) \((\w+)(?:,\s*(.+))?\)$")
_SLOT_TITLE_LOOSE_RE = re.compile(r"^(.+?) \((\w+)(?:,\s*(.+))?\).*$")
_RECURRENCE_DAY_RE = re.compile(r"<t:DaysOfWeek>([^<]+)</t:DaysOfWeek>")
_RECURRENCE_START_RE = re.compile(r"<t:StartDate>([^<]+)</t:StartDate>")
_RECURRENCE_END_RE = re.compile(r"<t:EndDate>([^<]+)</t:EndDate>")
_API_WEEKDAY_TO_PYTHON = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def parse_booking_datetime(value: str) -> dtm.datetime:
    parsed = dtm.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=MSK)
    return parsed.astimezone(MSK)


def _booking_categories_key(categories: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(category) for category in categories if str(category) != "Auto")


def _exchange_categories_key(categories: Iterable[Any]) -> tuple[str, ...]:
    sanitized: list[str] = []
    for category in categories:
        text = re.sub(r"[,;]", " ", str(category))
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s*/\s*$", "", text).strip()
        if text and text != "Auto":
            sanitized.append(text)
    return tuple(sanitized)


def auto_recurrence_fields(recurrence: Any) -> dict[str, Any] | None:
    """Read bounded weekly recurrence, including its interval, without assuming other patterns."""
    if isinstance(recurrence, dict):
        if recurrence.get("weekday") not in _API_WEEKDAY_TO_PYTHON:
            return None
        return dict(recurrence)
    if not isinstance(recurrence, str) or not recurrence.strip():
        return None
    try:
        root = ElementTree.fromstring(
            f'<root xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types">{recurrence}</root>'
        )
    except ElementTree.ParseError, DefusedXmlException:
        return None
    values = {node.tag.rsplit("}", 1)[-1]: (node.text or "").strip() for node in root.iter()}
    weekday = values.get("DaysOfWeek", "").lower()
    if (
        "WeeklyRecurrence" not in values
        or weekday not in _API_WEEKDAY_TO_PYTHON
        or not values.get("StartDate")
        or not values.get("EndDate")
    ):
        return None
    try:
        interval = int(values.get("Interval") or 1)
    except ValueError:
        return None
    if interval < 1:
        return None
    return {
        "weekday": weekday,
        "start_date": values["StartDate"][:10],
        "until_date": values["EndDate"][:10],
        "interval": interval,
    }


def _strip_forwarding_title_prefix(title: str) -> str:
    text = title.strip()
    while True:
        stripped = False
        for prefix in _BOOKING_TITLE_FORWARD_PREFIXES:
            if text.casefold().startswith(prefix.casefold()):
                text = text[len(prefix) :].strip()
                stripped = True
                break
        if not stripped:
            return text


def strip_auto_booking_title_prefix(title: str) -> str:
    text = _strip_forwarding_title_prefix(title)
    for prefix in _AUTO_TITLE_PREFIXES:
        if text.casefold().startswith(prefix.casefold()):
            return text[len(prefix) :].strip()
    return text


def is_schedule_assistant_auto_title(title: str) -> bool:
    text = _strip_forwarding_title_prefix(title)
    return any(text.casefold().startswith(prefix.casefold()) for prefix in _AUTO_TITLE_PREFIXES)


def _normalize_booking_title_for_parse(title: str) -> str:
    text = strip_auto_booking_title_prefix(title).strip()
    return _SCHEDULE_ASSISTANT_IU_TITLE_RE.sub("", text, count=1).strip()


def _parse_slot_title(title: str) -> tuple[str, str, str | None] | None:
    match = _SLOT_TITLE_RE.match(_normalize_booking_title_for_parse(title))
    if not match:
        return None
    audience = match.group(3)
    return match.group(1).strip(), match.group(2).strip(), audience.strip() if audience else None


def _course_and_component_from_title(title: str) -> tuple[str, str | None]:
    text = _normalize_booking_title_for_parse(title)
    match = _SLOT_TITLE_RE.match(text) or _SLOT_TITLE_LOOSE_RE.match(text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return text, None


def _program_code_from_booking_categories(categories: Iterable[Any]) -> str | None:
    parts = [str(category) for category in categories if str(category) != "Auto"]
    if len(parts) < 2:
        return None
    program = parts[1]
    if program in {"core", "elective"}:
        return None
    return program


def _course_name_from_booking_categories(categories: Iterable[Any]) -> str | None:
    parts = [str(category) for category in categories if str(category) != "Auto"]
    if not parts:
        return None
    return parts[-1]


def _course_names_match_for_auto(payload_course: str, booking_course: str) -> bool:
    if payload_course == booking_course:
        return True
    for separator in (":", " -", " —"):
        if booking_course.startswith(f"{payload_course}{separator}"):
            return True
        if payload_course.startswith(f"{booking_course}{separator}"):
            return True
    return False


def _program_codes_match_for_auto(payload_program: str, booking_program: str) -> bool:
    if payload_program == booking_program:
        return True
    return payload_program.split("/", 1)[0] == booking_program.split("/", 1)[0]


def _auto_booking_categories_match(payload_categories: list[Any], auto_categories: list[Any]) -> bool:
    payload_key = _booking_categories_key(payload_categories)
    auto_key = _booking_categories_key(auto_categories)
    if payload_key == auto_key:
        return True
    if len(payload_key) < 3 or len(auto_key) < 3:
        return False
    if payload_key[0] != auto_key[0]:
        return False
    if not _program_codes_match_for_auto(payload_key[1], auto_key[1]):
        return False
    return _course_names_match_for_auto(payload_key[-1], auto_key[-1])


def _auto_booking_metadata_matches(payload: dict[str, Any], auto_booking: dict[str, Any]) -> bool:
    payload_categories = payload.get("categories")
    auto_categories = auto_booking.get("categories")
    if not isinstance(payload_categories, list) or not isinstance(auto_categories, list):
        return False
    if _auto_booking_categories_match(payload_categories, auto_categories):
        return True
    if _exchange_categories_key(payload_categories) != _exchange_categories_key(auto_categories):
        return False
    payload_title = _normalize_booking_title_for_parse(str(payload.get("title") or ""))
    auto_title = _normalize_booking_title_for_parse(str(auto_booking.get("title") or ""))
    return bool(payload_title and payload_title == auto_title)


def _booking_identity_dict(booking: dict[str, Any]) -> dict[str, Any]:
    return {
        "room_id": booking.get("room_id"),
        "title": booking.get("title"),
        "start": booking.get("start"),
        "end": booking.get("end"),
        "categories": booking.get("categories"),
        "uid": booking.get("uid"),
        "operation_id": booking.get("operation_id"),
        "organizer_mailbox": booking.get("organizer_mailbox"),
        "outlook_booking_id": booking.get("outlook_booking_id"),
    }


def _slot_times_match_for_identity(
    booking_start: dtm.datetime,
    booking_end: dtm.datetime,
    payload_start: dtm.datetime,
    payload_end: dtm.datetime,
    booking_title: str,
) -> bool:
    start_match = booking_start.time() == payload_start.time()
    end_match = booking_end.time() == payload_end.time()
    return start_match and end_match


def booking_matches_payload_identity(booking: dict[str, Any], payload: dict[str, Any]) -> bool:
    if str(booking.get("room_id")) != str(payload.get("room_id")):
        return False

    booking_start = parse_booking_datetime(str(booking["start"]))
    booking_end = parse_booking_datetime(str(booking["end"]))
    payload_start = parse_booking_datetime(str(payload["start"]))
    payload_end = parse_booking_datetime(str(payload["end"]))
    payload_title = str(payload.get("title") or "")
    booking_title = str(booking.get("title") or "")
    if not _slot_times_match_for_identity(
        booking_start,
        booking_end,
        payload_start,
        payload_end,
        booking_title,
    ):
        return False

    if same_booking_identity(booking, payload):
        return True
    if payload_title == booking_title:
        return True
    if strip_auto_booking_title_prefix(booking_title) == payload_title:
        return True

    payload_parts = _parse_slot_title(payload_title)
    booking_parts = _parse_slot_title(booking_title)
    if payload_parts is None or booking_parts is None:
        return is_schedule_assistant_auto_title(booking_title) and (
            strip_auto_booking_title_prefix(booking_title) == payload_title
            or strip_auto_booking_title_prefix(booking_title) == strip_auto_booking_title_prefix(payload_title)
        )

    payload_course, payload_tag, payload_audience = payload_parts
    booking_course, booking_tag, booking_audience = booking_parts
    if payload_tag != booking_tag:
        return False
    if payload_course != booking_course and not (
        is_schedule_assistant_auto_title(booking_title) and _course_names_match_for_auto(payload_course, booking_course)
    ):
        return False

    payload_categories = payload.get("categories")
    booking_categories = booking.get("categories")
    payload_program = (
        _program_code_from_booking_categories(payload_categories) if isinstance(payload_categories, list) else None
    )
    booking_program = (
        _program_code_from_booking_categories(booking_categories) if isinstance(booking_categories, list) else None
    )
    if payload_program is None:
        payload_program = payload_audience
    if booking_program is None:
        booking_program = booking_audience

    if payload_program and booking_program:
        return payload_program == booking_program or (
            is_schedule_assistant_auto_title(booking_title)
            and _program_codes_match_for_auto(payload_program, booking_program)
        )

    if payload_program and not booking_program:
        return is_schedule_assistant_auto_title(booking_title)

    return not booking_program


def payload_matches_auto_booking(payload: dict[str, Any], auto_booking: dict[str, Any]) -> bool:
    if not _auto_booking_matches_weekly_payload_identity(payload, auto_booking):
        return False
    if not auto_booking.get("recurrence_complete", not bool(auto_booking.get("recurrence"))):
        return False
    expected = set(iter_payload_occurrences(payload))
    return bool(expected) and expected == set(iter_booking_occurrences(auto_booking))


def _auto_booking_matches_weekly_payload_identity(
    payload: dict[str, Any],
    auto_booking: dict[str, Any],
) -> bool:
    if str(payload.get("room_id")) != str(auto_booking.get("room_id")):
        return False
    if same_booking_identity(auto_booking, payload):
        return (
            parse_booking_datetime(str(payload["start"])).time()
            == parse_booking_datetime(str(auto_booking["start"])).time()
            and parse_booking_datetime(str(payload["end"])).time()
            == parse_booking_datetime(str(auto_booking["end"])).time()
        )

    payload_parts = _parse_slot_title(str(payload.get("title") or ""))
    booking_parts = _parse_slot_title(str(auto_booking.get("title") or ""))
    if payload_parts and booking_parts and payload_parts[1:] != booking_parts[1:]:
        return False
    payload_categories = payload.get("categories")
    auto_categories = auto_booking.get("categories")
    if isinstance(payload_categories, list) and isinstance(auto_categories, list):
        if not _auto_booking_metadata_matches(payload, auto_booking):
            return False
    elif not booking_matches_payload_identity(_booking_identity_dict(auto_booking), payload):
        return False

    payload_start = parse_booking_datetime(str(payload["start"]))
    payload_end = parse_booking_datetime(str(payload["end"]))
    auto_start = parse_booking_datetime(str(auto_booking["start"]))
    auto_end = parse_booking_datetime(str(auto_booking["end"]))
    return payload_start.time() == auto_start.time() and payload_end.time() == auto_end.time()


def _weekly_series_contains_date(payload_recurrence: dict[str, Any], meeting_date: dtm.date) -> bool:
    weekday = str(payload_recurrence.get("weekday", "")).strip().lower()
    series_start = dtm.date.fromisoformat(str(payload_recurrence["start_date"]))
    series_end = dtm.date.fromisoformat(str(payload_recurrence["until_date"]))
    target = _API_WEEKDAY_TO_PYTHON[weekday]
    first = series_start + dtm.timedelta(days=(target - series_start.weekday()) % 7)
    return (
        first <= meeting_date <= series_end
        and (meeting_date - first).days % (7 * int(payload_recurrence.get("interval", 1))) == 0
    )


def payload_matches_auto_occurrence(payload: dict[str, Any], auto_booking: dict[str, Any]) -> bool:
    payload_recurrence = payload.get("recurrence")
    if not isinstance(payload_recurrence, dict):
        return False
    if auto_recurrence_fields(auto_booking.get("recurrence")) is not None:
        return False
    if not _auto_booking_matches_weekly_payload_identity(payload, auto_booking):
        return False
    auto_start = parse_booking_datetime(str(auto_booking["start"]))
    return _weekly_series_contains_date(payload_recurrence, auto_start.date())


def payload_matches_auto_series(payload: dict[str, Any], auto_booking: dict[str, Any]) -> bool:
    return payload_matches_auto_booking(payload, auto_booking)


def find_matching_auto_booking(
    payload: dict[str, Any],
    auto_bookings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return a booking only when it covers every requested occurrence."""
    expected = set(iter_payload_occurrences(payload))
    for booking in auto_bookings:
        if not _auto_booking_matches_weekly_payload_identity(payload, booking):
            continue
        if not booking.get("recurrence_complete", not bool(booking.get("recurrence"))):
            continue
        if expected and expected <= set(iter_booking_occurrences(booking)):
            return booking
    return None


def auto_booking_matches_any_slot_payload(
    auto_booking: dict[str, Any],
    slot_payloads: list[dict[str, Any]],
) -> bool:
    actual = set(iter_booking_occurrences(auto_booking))
    expected = {
        occurrence
        for payload in slot_payloads
        if _auto_booking_matches_weekly_payload_identity(payload, auto_booking)
        for occurrence in iter_payload_occurrences(payload)
    }
    return bool(actual) and actual <= expected


def extra_booking_candidate_key(booking: dict[str, Any]) -> str | None:
    outlook_booking_id = booking.get("outlook_booking_id")
    if outlook_booking_id:
        mailbox = str(booking.get("organizer_mailbox") or "").casefold()
        return f"id:{mailbox}:{outlook_booking_id}" if mailbox else f"id:{outlook_booking_id}"
    outlook_entry_id = booking.get("outlook_entry_id")
    room_id = booking.get("room_id")
    if outlook_entry_id and room_id:
        return f"entry:{room_id}:{outlook_entry_id}"
    return None


def _collect_auto_booking_candidates(
    auto_bookings: list[dict[str, Any]],
    existing_bookings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen_keys: set[str] = set()
    candidates: list[dict[str, Any]] = []

    def append_candidate(booking: dict[str, Any]) -> None:
        key = extra_booking_candidate_key(booking)
        if key is None or key in seen_keys:
            return
        seen_keys.add(key)
        candidates.append(booking)

    for booking in auto_bookings:
        append_candidate(booking)
    for booking in existing_bookings:
        if not is_schedule_assistant_auto_title(str(booking.get("title") or "")):
            continue
        append_candidate(booking)
    return candidates


def find_extra_auto_bookings(
    auto_bookings: list[dict[str, Any]],
    slot_payloads: list[dict[str, Any]],
    *,
    existing_bookings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    extra: list[dict[str, Any]] = []
    for candidate in _collect_auto_booking_candidates(auto_bookings, existing_bookings or []):
        if auto_booking_matches_any_slot_payload(candidate, slot_payloads):
            continue
        extra.append(candidate)
    extra.sort(key=lambda item: str(item.get("start") or ""))
    return extra


def same_booking_identity(booking: dict[str, Any], reference: dict[str, Any]) -> bool:
    """Mailbox-scoped IDs or a shared UID prove identity; titles/time never do."""
    mailbox = booking.get("organizer_mailbox")
    reference_mailbox = reference.get("organizer_mailbox")
    if mailbox and reference_mailbox and str(mailbox).casefold() != str(reference_mailbox).casefold():
        return False
    for key in ("operation_id", "uid"):
        if booking.get(key) and booking.get(key) == reference.get(key):
            return True
    return bool(
        mailbox
        and reference_mailbox
        and booking.get("outlook_booking_id")
        and booking.get("outlook_booking_id") == reference.get("outlook_booking_id")
    )


def booking_in_own_auto_series(
    booking: dict[str, Any],
    payload: dict[str, Any],
    auto_bookings: list[dict[str, Any]],
) -> bool:
    expected = set(iter_payload_occurrences(payload))
    if same_booking_identity(booking, payload):
        return bool(expected & set(iter_booking_occurrences(booking)))
    for auto_booking in auto_bookings:
        if not _auto_booking_matches_weekly_payload_identity(payload, auto_booking):
            continue
        if not same_booking_identity(booking, auto_booking):
            continue
        if expected & set(iter_booking_occurrences(booking)) & set(iter_booking_occurrences(auto_booking)):
            return True
    return False


def iter_payload_occurrences(payload: dict[str, Any]) -> list[tuple[dtm.datetime, dtm.datetime]]:
    recurrence = payload.get("recurrence")
    if isinstance(recurrence, dict):
        weekday = str(recurrence["weekday"]).strip().lower()
        range_start = dtm.date.fromisoformat(str(recurrence["start_date"]))
        range_end = dtm.date.fromisoformat(str(recurrence["until_date"]))
        target = _API_WEEKDAY_TO_PYTHON[weekday]
        start_time = parse_booking_datetime(str(payload["start"])).time()
        end_time = parse_booking_datetime(str(payload["end"])).time()
        occurrences: list[tuple[dtm.datetime, dtm.datetime]] = []
        interval = int(recurrence.get("interval", 1))
        if interval < 1:
            raise ValueError("Weekly recurrence interval must be positive")
        current = range_start + dtm.timedelta(days=(target - range_start.weekday()) % 7)
        deleted = {str(value)[:10] for value in payload.get("deleted_occurrences", [])}
        while current <= range_end:
            if current.isoformat() not in deleted:
                start = dtm.datetime.combine(current, start_time).replace(tzinfo=MSK)
                end = dtm.datetime.combine(current, end_time).replace(tzinfo=MSK)
                occurrences.append((start, end))
            current += dtm.timedelta(weeks=interval)
        for modified in payload.get("modified_occurrences", []):
            original = parse_booking_datetime(str(modified["original_start"]))
            occurrences = [(start, end) for start, end in occurrences if start != original]
            occurrences.append(
                (parse_booking_datetime(str(modified["start"])), parse_booking_datetime(str(modified["end"])))
            )
        return sorted(occurrences)

    start = parse_booking_datetime(str(payload["start"]))
    end = parse_booking_datetime(str(payload["end"]))
    return [(start, end)]


def iter_booking_occurrences(booking: dict[str, Any]) -> list[tuple[dtm.datetime, dtm.datetime]]:
    recurrence = auto_recurrence_fields(booking.get("recurrence"))
    if booking.get("recurrence") and recurrence is None:
        return []
    return iter_payload_occurrences({**booking, "recurrence": recurrence})


@dataclass
class BookingCoverage:
    expected: set[tuple[dtm.datetime, dtm.datetime]] = field(default_factory=set)
    covered: set[tuple[dtm.datetime, dtm.datetime]] = field(default_factory=set)
    bookings: list[dict[str, Any]] = field(default_factory=list)
    uncertain: bool = False

    @property
    def missing(self) -> set[tuple[dtm.datetime, dtm.datetime]]:
        return self.expected - self.covered


def booking_coverage(
    payload: dict[str, Any],
    auto_bookings: list[dict[str, Any]],
    existing_bookings: list[dict[str, Any]] | None = None,
) -> BookingCoverage:
    result = BookingCoverage(expected=set(iter_payload_occurrences(payload)))
    for booking in auto_bookings:
        if not _auto_booking_matches_weekly_payload_identity(payload, booking):
            continue
        occurrences = set(iter_booking_occurrences(booking))
        matching = result.expected & occurrences
        if not matching and occurrences:
            continue
        result.bookings.append(booking)
        incomplete = not booking.get("recurrence_complete", not bool(booking.get("recurrence"))) or bool(
            booking.get("recurrence") and not occurrences
        )
        result.uncertain |= incomplete
        if not incomplete:
            result.covered.update(matching)
    for booking in existing_bookings or []:
        if not any(same_booking_identity(booking, own) for own in result.bookings):
            continue
        result.covered.update(result.expected & set(iter_booking_occurrences(booking)))
    return result


def detect_payload_conflicts(
    payload: dict[str, Any],
    existing_bookings: list[dict[str, Any]],
    *,
    auto_bookings: list[dict[str, Any]] | None = None,
) -> list[tuple[dtm.datetime, dtm.datetime, list[dict[str, Any]]]]:
    room_id = payload.get("room_id")
    if not room_id:
        return []

    hits: list[tuple[dtm.datetime, dtm.datetime, list[dict[str, Any]]]] = []
    for occurrence_start, occurrence_end in iter_payload_occurrences(payload):
        conflicts: list[dict[str, Any]] = []
        for booking in existing_bookings:
            if str(booking.get("room_id")) != str(room_id):
                continue
            if str(booking.get("busy_type") or "").casefold() == "free":
                continue
            if not any(
                occurrence_start < existing_end and existing_start < occurrence_end
                for existing_start, existing_end in iter_booking_occurrences(booking)
            ):
                continue
            if booking_in_own_auto_series(booking, payload, auto_bookings or []):
                continue
            conflicts.append(booking)
        if conflicts:
            hits.append((occurrence_start, occurrence_end, conflicts))
    return hits
