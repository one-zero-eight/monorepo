from src.schedule_assistant.modules.issues.booking_match import booking_matches_payload, slot_has_matching_booking


def _payload() -> dict:
    return {
        "room_id": "107",
        "title": "Algorithms (lec)",
        "start": "2026-06-08T14:20:00+03:00",
        "end": "2026-06-08T15:50:00+03:00",
        "categories": ["core", "BS_Y1", "Algorithms"],
    }


def test_booking_matches_payload_by_auto_title() -> None:
    payload = _payload()
    booking = {
        "room_id": "107",
        "title": "Schedule Assistant IU Auto: Algorithms (lec)",
        "start": "2026-06-08T14:20:00+03:00",
        "end": "2026-06-08T15:50:00+03:00",
        "categories": ["Auto", "core", "BS_Y1", "Algorithms"],
    }
    assert booking_matches_payload(booking, payload)


def test_booking_matches_payload_by_categories_and_time() -> None:
    payload = _payload()
    booking = {
        "room_id": "107",
        "title": "Different title",
        "start": "2026-06-08T14:20:00+03:00",
        "end": "2026-06-08T15:50:00+03:00",
        "categories": ["Auto", "core", "BS_Y1", "Algorithms"],
        "recurrence": None,
    }
    assert booking_matches_payload(booking, payload)


def test_slot_has_matching_booking_from_room_calendar() -> None:
    payload = _payload()
    existing = [
        {
            "room_id": "107",
            "title": "Schedule Assistant IU Auto: Algorithms (lec)",
            "start": "2026-06-08T14:20:00+03:00",
            "end": "2026-06-08T15:50:00+03:00",
            "categories": ["Auto", "core", "BS_Y1", "Algorithms"],
        },
    ]
    assert slot_has_matching_booking(payload, auto_bookings=[], existing_bookings=existing)


def test_slot_has_no_matching_booking() -> None:
    payload = _payload()
    existing = [
        {
            "room_id": "107",
            "title": "Other course (lec)",
            "start": "2026-06-08T14:20:00+03:00",
            "end": "2026-06-08T15:50:00+03:00",
            "categories": ["core", "BS_Y1", "Other course"],
        },
    ]
    assert not slot_has_matching_booking(payload, auto_bookings=[], existing_bookings=existing)


def test_weekly_payload_matches_single_calendar_instance() -> None:
    payload = {
        "room_id": "107",
        "title": "Algorithms (lec)",
        "start": "2026-06-08T14:20:00+03:00",
        "end": "2026-06-08T15:50:00+03:00",
        "categories": ["core", "BS_Y1", "Algorithms"],
        "recurrence": {
            "kind": "weekly_until",
            "weekday": "monday",
            "start_date": "2026-06-01",
            "until_date": "2026-08-02",
        },
    }
    booking = {
        "room_id": "107",
        "title": "Schedule Assistant IU Auto: Algorithms (lec)",
        "start": "2026-06-15T14:20:00+03:00",
        "end": "2026-06-15T15:50:00+03:00",
        "categories": ["Auto", "core", "BS_Y1", "Algorithms"],
    }
    assert booking_matches_payload(booking, payload)
