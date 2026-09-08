import datetime as dtm
from typing import Any

from src.schedule_assistant.modules.bookings.client import BookingDTO
from src.schedule_assistant.modules.bookings.match import (
    booking_coverage,
    booking_in_own_auto_series,
    booking_matches_payload_identity,
    iter_booking_occurrences,
    iter_payload_occurrences,
    payload_matches_auto_booking,
)


def booking_as_dict(booking: BookingDTO) -> dict[str, Any]:
    data = booking.model_dump(mode="json")
    data["start"] = data.pop("start_time")
    data["end"] = data.pop("end_time")
    return data


def booking_matches_payload(booking: dict[str, Any], payload: dict[str, Any]) -> bool:
    """A candidate occurrence match, not evidence of complete series coverage."""
    if not (booking_matches_payload_identity(booking, payload) or payload_matches_auto_booking(payload, booking)):
        return False
    return bool(set(iter_payload_occurrences(payload)) & set(iter_booking_occurrences(booking)))


def slot_has_matching_booking(
    payload: dict[str, Any],
    *,
    auto_bookings: list[dict[str, Any]],
    existing_bookings: list[dict[str, Any]],
) -> bool:
    coverage = booking_coverage(payload, auto_bookings, existing_bookings)
    return bool(coverage.expected) and not coverage.missing and not coverage.uncertain


def detect_payload_conflicts(
    payload: dict[str, Any],
    existing_bookings: list[BookingDTO],
) -> list[tuple[dtm.datetime, dtm.datetime, list[BookingDTO]]]:
    room_id = payload.get("room_id")
    if not room_id:
        return []
    hits: list[tuple[dtm.datetime, dtm.datetime, list[BookingDTO]]] = []
    for occurrence_start, occurrence_end in iter_payload_occurrences(payload):
        conflicts = []
        for booking in existing_bookings:
            data = booking_as_dict(booking)
            if str(booking.room_id) != str(room_id) or str(data.get("busy_type") or "").lower() == "free":
                continue
            if not any(
                occurrence_start < end and start < occurrence_end for start, end in iter_booking_occurrences(data)
            ):
                continue
            if booking_in_own_auto_series(data, payload, []):
                continue
            conflicts.append(booking)
        if conflicts:
            hits.append((occurrence_start, occurrence_end, conflicts))
    return hits
