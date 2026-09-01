import datetime as dtm
import re
import unicodedata
from collections.abc import Iterable
from typing import Any
from zoneinfo import ZoneInfo

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


def auto_recurrence_fields(recurrence: Any) -> dict[str, str] | None:
    if not isinstance(recurrence, str):
        return None
    day_match = _RECURRENCE_DAY_RE.search(recurrence)
    if not day_match:
        return None
    start_match = _RECURRENCE_START_RE.search(recurrence)
    end_match = _RECURRENCE_END_RE.search(recurrence)
    return {
        "weekday": day_match.group(1).strip().lower(),
        "start_date": start_match.group(1).strip() if start_match else "",
        "until_date": end_match.group(1).strip() if end_match else "",
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


def _course_names_match_for_component_conflict(payload_course: str, booking_course: str) -> bool:
    if _course_names_match_for_auto(payload_course, booking_course):
        return True
    payload_normalized = payload_course.casefold().strip()
    booking_normalized = booking_course.casefold().strip()
    if not payload_normalized or not booking_normalized:
        return False
    return booking_normalized.startswith(f"{payload_normalized} ") or payload_normalized.startswith(
        f"{booking_normalized} "
    )


def _course_names_match_via_categories(booking: dict[str, Any], payload: dict[str, Any]) -> bool:
    payload_categories = payload.get("categories")
    booking_categories = booking.get("categories")
    if not isinstance(payload_categories, list) or not isinstance(booking_categories, list):
        return False
    payload_course = _course_name_from_booking_categories(payload_categories)
    booking_course = _course_name_from_booking_categories(booking_categories)
    if not payload_course or not booking_course:
        return False
    return _course_names_match_for_auto(payload_course, booking_course)


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
    if start_match and end_match:
        return True
    return is_schedule_assistant_auto_title(booking_title) and start_match


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
    if str(payload.get("room_id")) != str(auto_booking.get("room_id")):
        return False

    if not _auto_booking_metadata_matches(payload, auto_booking):
        return False

    payload_start = parse_booking_datetime(str(payload["start"]))
    payload_end = parse_booking_datetime(str(payload["end"]))
    auto_start = parse_booking_datetime(str(auto_booking["start"]))
    auto_end = parse_booking_datetime(str(auto_booking["end"]))
    if payload_start.time() != auto_start.time() or payload_end.time() != auto_end.time():
        return False

    payload_recurrence = payload.get("recurrence")
    auto_recurrence = auto_recurrence_fields(auto_booking.get("recurrence"))
    if isinstance(payload_recurrence, dict):
        if auto_recurrence is None:
            return False
        if str(payload_recurrence.get("weekday", "")).strip().lower() != auto_recurrence["weekday"]:
            return False
        if str(payload_recurrence.get("start_date", "")) != auto_recurrence["start_date"]:
            return False
        return str(payload_recurrence.get("until_date", "")) == auto_recurrence["until_date"]

    if auto_recurrence is not None:
        return False
    return payload_start.date() == auto_start.date() and payload_end.date() == auto_end.date()


def _auto_booking_matches_weekly_payload_identity(
    payload: dict[str, Any],
    auto_booking: dict[str, Any],
) -> bool:
    if str(payload.get("room_id")) != str(auto_booking.get("room_id")):
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
    return series_start <= meeting_date <= series_end and meeting_date.weekday() == target


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
    if not _auto_booking_matches_weekly_payload_identity(payload, auto_booking):
        return False

    payload_recurrence = payload.get("recurrence")
    auto_recurrence = auto_recurrence_fields(auto_booking.get("recurrence"))
    if isinstance(payload_recurrence, dict):
        if auto_recurrence is None:
            return False
        if str(payload_recurrence.get("weekday", "")).strip().lower() != auto_recurrence["weekday"]:
            return False
        return str(payload_recurrence.get("until_date", "")) == auto_recurrence["until_date"]

    if auto_recurrence is not None:
        return False
    payload_start = parse_booking_datetime(str(payload["start"]))
    auto_start = parse_booking_datetime(str(auto_booking["start"]))
    payload_end = parse_booking_datetime(str(payload["end"]))
    auto_end = parse_booking_datetime(str(auto_booking["end"]))
    return payload_start.date() == auto_start.date() and payload_end.date() == auto_end.date()


def find_matching_auto_booking(
    payload: dict[str, Any],
    auto_bookings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for auto_booking in auto_bookings:
        if payload_matches_auto_booking(payload, auto_booking):
            return auto_booking
        if payload_matches_auto_series(payload, auto_booking):
            return auto_booking
        if payload_matches_auto_occurrence(payload, auto_booking):
            return auto_booking
    return None


def auto_booking_matches_any_slot_payload(
    auto_booking: dict[str, Any],
    slot_payloads: list[dict[str, Any]],
) -> bool:
    for payload in slot_payloads:
        if payload_matches_auto_booking(payload, auto_booking):
            return True
        if payload_matches_auto_series(payload, auto_booking):
            return True
        if payload_matches_auto_occurrence(payload, auto_booking):
            return True
    return False


def extra_booking_candidate_key(booking: dict[str, Any]) -> str | None:
    outlook_booking_id = booking.get("outlook_booking_id")
    if outlook_booking_id:
        return f"id:{outlook_booking_id}"
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


def _same_time_and_categories(booking: dict[str, Any], reference: dict[str, Any]) -> bool:
    if str(booking.get("room_id")) != str(reference.get("room_id")):
        return False
    booking_categories = booking.get("categories")
    reference_categories = reference.get("categories")
    if (
        isinstance(booking_categories, list)
        and isinstance(reference_categories, list)
        and _booking_categories_key(booking_categories) != _booking_categories_key(reference_categories)
    ):
        return False
    booking_start = parse_booking_datetime(str(booking["start"]))
    booking_end = parse_booking_datetime(str(booking["end"]))
    reference_start = parse_booking_datetime(str(reference["start"]))
    reference_end = parse_booking_datetime(str(reference["end"]))
    return booking_start.time() == reference_start.time() and booking_end.time() == reference_end.time()


def _booking_overlaps_auto_instance(booking: dict[str, Any], auto_booking: dict[str, Any]) -> bool:
    auto_as_payload = _booking_identity_dict(auto_booking)
    if not booking_matches_payload_identity(booking, auto_as_payload) and not _same_time_and_categories(
        booking, auto_booking
    ):
        return False

    auto_recurrence = auto_recurrence_fields(auto_booking.get("recurrence"))
    booking_start = parse_booking_datetime(str(booking["start"]))
    if auto_recurrence is None:
        auto_start = parse_booking_datetime(str(auto_booking["start"]))
        return booking_start.date() == auto_start.date()

    series_start = dtm.date.fromisoformat(auto_recurrence["start_date"])
    series_end = dtm.date.fromisoformat(auto_recurrence["until_date"])
    weekday = _API_WEEKDAY_TO_PYTHON[auto_recurrence["weekday"]]
    return series_start <= booking_start.date() <= series_end and booking_start.weekday() == weekday


def _booking_is_same_course_component(booking: dict[str, Any], payload: dict[str, Any]) -> bool:
    payload_parts = _parse_slot_title(str(payload.get("title") or ""))
    if payload_parts is None:
        return False
    payload_course, payload_tag, _ = payload_parts
    booking_course, booking_tag = _course_and_component_from_title(str(booking.get("title") or ""))
    course_match = _course_names_match_for_component_conflict(payload_course, booking_course)
    if not course_match:
        course_match = _course_names_match_via_categories(booking, payload)
    if not course_match:
        return False
    return booking_tag is None or booking_tag == payload_tag


def booking_in_own_auto_series(
    booking: dict[str, Any],
    payload: dict[str, Any],
    auto_bookings: list[dict[str, Any]],
) -> bool:
    if booking_matches_payload_identity(booking, payload):
        return True
    if _booking_is_same_course_component(booking, payload):
        return True
    if payload_matches_auto_booking(payload, booking):
        return True

    for auto_booking in auto_bookings:
        if not (
            payload_matches_auto_booking(payload, auto_booking)
            or payload_matches_auto_series(payload, auto_booking)
            or payload_matches_auto_occurrence(payload, auto_booking)
        ):
            continue
        if _booking_overlaps_auto_instance(booking, auto_booking):
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
        current = range_start
        while current <= range_end:
            if current.weekday() == target:
                start = dtm.datetime.combine(current, start_time).replace(tzinfo=MSK)
                end = dtm.datetime.combine(current, end_time).replace(tzinfo=MSK)
                occurrences.append((start, end))
            current += dtm.timedelta(days=1)
        return occurrences

    start = parse_booking_datetime(str(payload["start"]))
    end = parse_booking_datetime(str(payload["end"]))
    return [(start, end)]


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
            existing_start = parse_booking_datetime(str(booking["start"]))
            existing_end = parse_booking_datetime(str(booking["end"]))
            if not (occurrence_start < existing_end and existing_start < occurrence_end):
                continue
            if booking_in_own_auto_series(booking, payload, auto_bookings or []):
                continue
            conflicts.append(booking)
        if conflicts:
            hits.append((occurrence_start, occurrence_end, conflicts))
    return hits
