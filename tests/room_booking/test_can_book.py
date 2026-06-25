import datetime as dtm
from typing import Literal

import pytest

from src.inh_accounts_sdk import InnopolisInfo, UserSchema
from src.room_booking.config_schema import Room
from src.room_booking.modules.rules import service as rules_service
from src.room_booking.modules.rules.service import can_book, can_use_recurrence
from tests.room_booking.datetime_helpers import msk


def _room(
    id: str = "3.1",
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


def _user(
    *,
    email: str = "student@innopolis.university",
    is_student: bool = True,
    is_staff: bool = False,
) -> InnopolisInfo:
    return InnopolisInfo(
        email=email,
        is_student=is_student,
        is_staff=is_staff,
        updated_at=dtm.datetime.now(dtm.UTC),
    )


def test_can_book_start_not_before_end():
    now = msk(2025, 1, 6, 12)
    ok, msg = can_book(
        user=_user(),
        room=_room(),
        start=msk(2025, 1, 6, 14),
        end=msk(2025, 1, 6, 13),
        now=now,
    )
    assert ok is False
    assert msg == "Start must be before end."


def test_can_book_in_the_past():
    now = msk(2025, 1, 6, 12)
    ok, msg = can_book(
        user=_user(),
        room=_room(),
        start=msk(2025, 1, 6, 10),
        end=msk(2025, 1, 6, 11),
        now=now,
    )
    assert ok is False
    assert msg == "Booking cannot be in the past."


def test_can_book_is_update_allows_currently_running():
    now = msk(2025, 1, 6, 12)
    ok, msg = can_book(
        user=_user(),
        room=_room(),
        start=msk(2025, 1, 6, 11),
        end=msk(2025, 1, 6, 13),
        now=now,
        is_update=True,
    )
    assert ok is True
    assert not msg


def test_can_book_more_than_two_weeks_in_future():
    now = msk(2025, 1, 6, 12)
    ok, msg = can_book(
        user=_user(),
        room=_room(),
        start=msk(2025, 1, 22, 13),
        end=msk(2025, 1, 22, 14),
        now=now,
    )
    assert ok is False
    assert "two weeks" in msg


def test_can_book_college_student_denied(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rules_service.room_repository, "user_has_access_to_room", lambda *_: False)
    now = msk(2025, 1, 6, 20)
    ok, msg = can_book(
        user=_user(is_student=False, is_staff=False),
        room=_room(),
        start=msk(2025, 1, 6, 21),
        end=msk(2025, 1, 6, 22),
        now=now,
    )
    assert ok is False
    assert "student or staff" in msg


def test_can_book_staff_yellow_allowed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rules_service.room_repository, "user_has_access_to_room", lambda *_: False)
    now = msk(2025, 1, 6, 20)
    ok, msg = can_book(
        user=_user(is_student=False, is_staff=True),
        room=_room(access_level="yellow"),
        start=msk(2025, 1, 6, 21),
        end=msk(2025, 1, 6, 22),
        now=now,
    )
    assert ok is True
    assert not msg


def test_can_book_student_yellow_allowed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rules_service.room_repository, "user_has_access_to_room", lambda *_: False)
    now = msk(2025, 1, 6, 20)
    ok, msg = can_book(
        user=_user(),
        room=_room(access_level="yellow"),
        start=msk(2025, 1, 6, 21),
        end=msk(2025, 1, 6, 22),
        now=now,
    )
    assert ok is True
    assert not msg


def test_can_book_uses_access_list(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(rules_service.room_repository, "user_has_access_to_room", lambda *_: True)
    now = msk(2025, 1, 6, 20)
    ok, msg = can_book(
        user=_user(),
        room=_room(id="309A", access_level="special"),
        start=msk(2025, 1, 6, 21),
        end=msk(2025, 1, 7, 1),
        now=now,
    )
    assert ok is False
    assert "309A" in msg


def test_is_restricted_time_weekday_during_lecture_hours():
    start = msk(2025, 1, 6, 10)
    end = msk(2025, 1, 6, 11)
    assert rules_service._is_restricted_time(start=start, end=end) is True


def test_is_restricted_time_weekday_early_morning_not_restricted():
    start = msk(2025, 1, 6, 6)
    end = msk(2025, 1, 6, 7)
    assert rules_service._is_restricted_time(start=start, end=end) is False


def test_is_restricted_time_weekday_evening_not_restricted():
    start = msk(2025, 1, 6, 19)
    end = msk(2025, 1, 6, 20)
    assert rules_service._is_restricted_time(start=start, end=end) is False


def test_is_restricted_time_weekend_not_restricted():
    start = msk(2025, 1, 11, 10)
    end = msk(2025, 1, 11, 11)
    assert rules_service._is_restricted_time(start=start, end=end) is False


def test_is_restricted_time_cross_midnight_outside_lecture_window():
    start = msk(2025, 1, 6, 20)
    end = msk(2025, 1, 7, 7)
    assert rules_service._is_restricted_time(start=start, end=end) is False


def _user_schema(*, is_staff: bool = False, innohassle_admin: bool = False) -> UserSchema:
    return UserSchema(
        id="u1",
        innopolis_info=InnopolisInfo(
            email="user@innopolis.university",
            is_staff=is_staff,
            updated_at=dtm.datetime.now(dtm.UTC),
        ),
        innohassle_admin=innohassle_admin,
    )


def test_can_use_recurrence_none_user():
    assert can_use_recurrence(email="user@innopolis.university", user=None) is False


def test_can_use_recurrence_admin():
    assert can_use_recurrence(email="admin@innopolis.university", user=_user_schema(innohassle_admin=True)) is True


def test_can_use_recurrence_staff():
    assert can_use_recurrence(email="staff@innopolis.university", user=_user_schema(is_staff=True)) is True


def test_can_use_recurrence_student_denied():
    assert can_use_recurrence(email="student@innopolis.university", user=_user_schema()) is False
