from typing import Literal

from src.room_booking.config_schema import Room
from src.room_booking.modules.rules.service import check_rules


def _room(
    id: str = "101",
    access_level: Literal["yellow", "red", "special"] | None = "yellow",
    restrict_daytime: bool = False,
) -> Room:
    return Room(
        id=id,
        title="Room",
        short_name="R",
        resource_email=f"{id}@room",
        access_level=access_level,
        restrict_daytime=restrict_daytime,
    )


def test_none_role_denied():
    ok, msg = check_rules(
        room=_room(),
        booking_longer_than_3_hours=False,
        highest_role="none",
        in_access_list=False,
        is_restricted_time=False,
    )
    assert ok is False
    assert "student or staff" in msg


def test_309a_long_booking_in_access_list_denied():
    ok, msg = check_rules(
        room=_room(id="309A"),
        booking_longer_than_3_hours=True,
        highest_role="staff",
        in_access_list=True,
        is_restricted_time=False,
    )
    assert ok is False
    assert "309A" in msg and "3 hours" in msg


def test_staff_yellow_room_allowed():
    ok, msg = check_rules(
        room=_room(access_level="yellow"),
        booking_longer_than_3_hours=True,
        highest_role="staff",
        in_access_list=False,
        is_restricted_time=False,
    )
    assert ok is True
    assert not msg


def test_staff_red_room_allowed():
    ok, msg = check_rules(
        room=_room(access_level="red"),
        booking_longer_than_3_hours=True,
        highest_role="staff",
        in_access_list=False,
        is_restricted_time=False,
    )
    assert ok is True
    assert not msg


def test_staff_in_access_list_allowed():
    ok, msg = check_rules(
        room=_room(id="X", access_level="special"),
        booking_longer_than_3_hours=False,
        highest_role="staff",
        in_access_list=True,
        is_restricted_time=False,
    )
    assert ok is True
    assert not msg


def test_staff_not_in_access_list_special_room_denied():
    ok, msg = check_rules(
        room=_room(id="X", access_level="special"),
        booking_longer_than_3_hours=False,
        highest_role="staff",
        in_access_list=False,
        is_restricted_time=False,
    )
    assert ok is False
    assert "don't have rights" in msg


def test_student_long_booking_in_access_list_allowed():
    ok, msg = check_rules(
        room=_room(),
        booking_longer_than_3_hours=True,
        highest_role="student",
        in_access_list=True,
        is_restricted_time=False,
    )
    assert ok is True
    assert not msg


def test_student_long_booking_yellow_not_in_access_list_denied():
    ok, msg = check_rules(
        room=_room(access_level="yellow"),
        booking_longer_than_3_hours=True,
        highest_role="student",
        in_access_list=False,
        is_restricted_time=False,
    )
    assert ok is False
    assert "more than 3 hours" in msg


def test_in_access_list_allowed():
    ok, msg = check_rules(
        room=_room(),
        booking_longer_than_3_hours=False,
        highest_role="student",
        in_access_list=True,
        is_restricted_time=False,
    )
    assert ok is True
    assert not msg


def test_student_red_room_denied():
    ok, msg = check_rules(
        room=_room(access_level="red"),
        booking_longer_than_3_hours=False,
        highest_role="student",
        in_access_list=False,
        is_restricted_time=False,
    )
    assert ok is False
    assert "red access level" in msg


def test_yellow_not_restrict_daytime_allowed():
    ok, msg = check_rules(
        room=_room(access_level="yellow", restrict_daytime=False),
        booking_longer_than_3_hours=False,
        highest_role="student",
        in_access_list=False,
        is_restricted_time=False,
    )
    assert ok is True
    assert not msg


def test_yellow_restrict_daytime_restricted_time_denied():
    ok, msg = check_rules(
        room=_room(access_level="yellow", restrict_daytime=True),
        booking_longer_than_3_hours=False,
        highest_role="student",
        in_access_list=False,
        is_restricted_time=True,
    )
    assert ok is False
    assert "working hours" in msg or "lecture" in msg


def test_yellow_restrict_daytime_not_restricted_time_allowed():
    ok, msg = check_rules(
        room=_room(access_level="yellow", restrict_daytime=True),
        booking_longer_than_3_hours=False,
        highest_role="student",
        in_access_list=False,
        is_restricted_time=False,
    )
    assert ok is True
    assert not msg


def test_fallback_denied():
    ok, msg = check_rules(
        room=_room(id="X", access_level="special"),
        booking_longer_than_3_hours=False,
        highest_role="student",
        in_access_list=False,
        is_restricted_time=False,
    )
    assert ok is False
    assert "don't have rights" in msg
