from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.inh_accounts_sdk import UserTokenData
from src.room_booking.config_schema import Room
from src.room_booking.dependencies import AuthContext
from src.room_booking.modules.bookings import service as bookings_service
from src.room_booking.modules.bookings.schemas import Attendee, Booking
from src.room_booking.modules.bookings.service import (
    apply_related_to_me,
    calendar_item_to_booking,
    set_related_to_me,
)
from tests.room_booking.datetime_helpers import msk


def _booking(*, attendees: list[Attendee] | None = None) -> Booking:
    return Booking(
        room_id="3.1",
        title="Test",
        start=msk(2025, 1, 6, 10),
        end=msk(2025, 1, 6, 11),
        outlook_booking_id="booking-1",
        outlook_entry_id=None,
        attendees=attendees,
    )


def test_set_related_to_me_match():
    booking = _booking(attendees=[Attendee(email="me@innopolis.university", status=None, assosiated_room_id=None)])
    result = set_related_to_me(booking, "me@innopolis.university")
    assert result.related_to_me is True


def test_set_related_to_me_no_match():
    booking = _booking(attendees=[Attendee(email="other@innopolis.university", status=None, assosiated_room_id=None)])
    result = set_related_to_me(booking, "me@innopolis.university")
    assert result.related_to_me is False


def test_set_related_to_me_no_attendees():
    booking = _booking(attendees=None)
    result = set_related_to_me(booking, "me@innopolis.university")
    assert result.related_to_me is None


def test_set_related_to_me_list():
    bookings = [
        _booking(attendees=[Attendee(email="me@innopolis.university", status=None, assosiated_room_id=None)]),
        _booking(attendees=[Attendee(email="other@innopolis.university", status=None, assosiated_room_id=None)]),
    ]
    result = set_related_to_me(bookings, "me@innopolis.university")
    assert result[0].related_to_me is True
    assert result[1].related_to_me is False


def test_apply_related_to_me_service_passthrough():
    bookings = [_booking(attendees=[Attendee(email="me@innopolis.university", status=None, assosiated_room_id=None)])]
    result = apply_related_to_me(bookings, AuthContext(user=None, is_service=True))
    assert result[0].related_to_me is None


def test_apply_related_to_me_user():
    bookings = [_booking(attendees=[Attendee(email="me@innopolis.university", status=None, assosiated_room_id=None)])]
    auth = AuthContext(
        user=UserTokenData(innohassle_id="u1", email="me@innopolis.university"),
        is_service=False,
    )
    result = apply_related_to_me(bookings, auth)
    assert result[0].related_to_me is True


def _room() -> Room:
    return Room(
        id="3.1",
        title="Meeting Room 3.1",
        short_name="3.1",
        resource_email="iu.resource.meetingroom.3.1@innopolis.ru",
        access_level="yellow",
    )


def _calendar_item(
    *,
    room_email: str = "iu.resource.meetingroom.3.1@innopolis.ru",
    participant_email: str = "user@innopolis.university",
) -> MagicMock:
    room_attendee = MagicMock()
    room_attendee.mailbox.email_address = room_email
    room_attendee.response_type = "Accept"

    user_attendee = MagicMock()
    user_attendee.mailbox.email_address = participant_email
    user_attendee.response_type = "Accept"

    item = MagicMock()
    item.required_attendees = [user_attendee]
    item.resources = [room_attendee]
    item.subject = "Meeting"
    item.start = msk(2025, 1, 6, 10)
    item.end = msk(2025, 1, 6, 11)
    item.id = "ews-id-1"
    item.categories = None
    item.recurrence = None
    item.account.version = SimpleNamespace(build="15.0.0")
    item.my_response_type = "Accept"
    return item


def test_calendar_item_to_booking_resolves_room_from_attendees(monkeypatch: pytest.MonkeyPatch):
    room = _room()
    monkeypatch.setattr(
        bookings_service.room_repository, "get_by_email", lambda email: room if email == room.resource_email else None
    )

    booking = calendar_item_to_booking(_calendar_item())

    assert booking is not None
    assert booking.room_id == "3.1"
    assert booking.outlook_booking_id == "ews-id-1"
    assert booking.outlook_entry_id is None


def test_calendar_item_to_booking_room_calendar_path(monkeypatch: pytest.MonkeyPatch):
    room = _room()
    monkeypatch.setattr(
        bookings_service.room_repository, "get_by_id", lambda room_id: room if room_id == "3.1" else None
    )
    monkeypatch.setattr(
        bookings_service.room_repository, "get_by_email", lambda email: room if email == room.resource_email else None
    )

    item = _calendar_item()
    item.resources = []
    item.required_attendees = [
        MagicMock(mailbox=MagicMock(email_address="user@innopolis.university"), response_type="Accept")
    ]

    booking = calendar_item_to_booking(
        item,
        room_id="3.1",
        was_fetched_from_room_calendar=True,
        room_calendar_entry_id="entry-hex",
        recurrence_xml="<recurrence/>",
    )

    assert booking is not None
    assert booking.outlook_entry_id == "entry-hex"
    assert booking.outlook_booking_id is None
    assert booking.recurrence == "<recurrence/>"
    assert booking.attendees is not None
    assert booking.attendees[0].email == room.resource_email


def test_calendar_item_to_booking_missing_room_returns_none(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(bookings_service.room_repository, "get_by_email", lambda _email: None)

    booking = calendar_item_to_booking(_calendar_item())

    assert booking is None
