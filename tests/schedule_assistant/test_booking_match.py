from src.schedule_assistant.modules.bookings.match import (
    find_extra_auto_bookings,
    payload_matches_auto_booking,
)
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


def test_cyrillic_course_category_removed_by_exchange_still_matches() -> None:
    payload = {
        "room_id": "318",
        "title": "Прикладная статистика в анализе данных (lec)",
        "start": "2026-08-24T14:20:00+03:00",
        "end": "2026-08-24T15:50:00+03:00",
        "categories": ["core", "B24-MFAI-01", "Прикладная статистика в анализе данных"],
        "recurrence": {
            "kind": "weekly_until",
            "weekday": "monday",
            "start_date": "2026-08-24",
            "until_date": "2026-12-21",
        },
    }
    booking = {
        "room_id": "318",
        "title": "Auto: Прикладная статистика в анализе данных (lec)",
        "start": "2026-08-24T14:20:00+03:00",
        "end": "2026-08-24T15:50:00+03:00",
        "categories": ["Auto", "core", "B24-MFAI-01"],
        "recurrence": (
            "<t:WeeklyRecurrence><t:DaysOfWeek>Monday</t:DaysOfWeek></t:WeeklyRecurrence>"
            "<t:StartDate>2026-08-24</t:StartDate><t:EndDate>2026-12-21</t:EndDate>"
        ),
        "outlook_booking_id": "booking-1",
    }

    assert payload_matches_auto_booking(payload, booking)
    assert find_extra_auto_bookings([booking], [payload]) == []


def test_sanitized_categories_require_exact_title() -> None:
    payload = {
        "room_id": "318",
        "title": "Прикладная статистика в анализе данных (lec)",
        "start": "2026-08-24T14:20:00+03:00",
        "end": "2026-08-24T15:50:00+03:00",
        "categories": ["core", "B24-MFAI-01", "Прикладная статистика в анализе данных"],
        "recurrence": {
            "kind": "weekly_until",
            "weekday": "monday",
            "start_date": "2026-08-24",
            "until_date": "2026-12-21",
        },
    }
    booking = {
        "room_id": "318",
        "title": "Auto: Другой предмет (lec)",
        "start": "2026-08-24T14:20:00+03:00",
        "end": "2026-08-24T15:50:00+03:00",
        "categories": ["Auto", "core", "B24-MFAI-01"],
        "recurrence": (
            "<t:WeeklyRecurrence><t:DaysOfWeek>Monday</t:DaysOfWeek></t:WeeklyRecurrence>"
            "<t:StartDate>2026-08-24</t:StartDate><t:EndDate>2026-12-21</t:EndDate>"
        ),
        "outlook_booking_id": "booking-1",
    }

    assert not payload_matches_auto_booking(payload, booking)
    assert find_extra_auto_bookings([booking], [payload]) == [booking]
