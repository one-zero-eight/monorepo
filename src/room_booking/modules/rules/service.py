import datetime as dtm
from typing import Literal

from src.inh_accounts_sdk import InnopolisInfo, UserSchema
from src.room_booking.modules.bookings.exchange_repository import to_msk
from src.room_booking.modules.rooms.repository import Room, room_repository

type Role = Literal["none", "student", "staff"]


def can_use_recurrence(*, email: str, user: UserSchema | None = None) -> bool:
    if user is None:
        return False
    if user.innohassle_admin:
        return True
    return user.innopolis_info.is_staff


def can_book(
    *,
    user: InnopolisInfo,
    room: Room,
    start: dtm.datetime,
    end: dtm.datetime,
    now: dtm.datetime | None = None,
    is_update: bool = False,
) -> tuple[bool, str]:  # TODO: add check against conflicts in the Outlook.
    start = to_msk(start)
    end = to_msk(end)
    current = to_msk(now) if now is not None else to_msk(dtm.datetime.now(dtm.UTC))

    if start >= end:
        return False, "Start must be before end."

    if (start < current and not is_update) or end < current:  # Allow to change currently-running booking
        return False, "Booking cannot be in the past."

    if abs((start - current).total_seconds()) > 14 * 24 * 3600:
        return False, "Booking cannot be more than two weeks in the future."

    in_access_list = room_repository.user_has_access_to_room(user.email, room.id)
    booking_longer_than_3_hours = end - start > dtm.timedelta(hours=3)

    highest_role: Role = "none"
    if user.is_student:
        highest_role = "student"
    if user.is_staff:
        highest_role = "staff"

    return check_rules(
        room=room,
        booking_longer_than_3_hours=booking_longer_than_3_hours,
        highest_role=highest_role,
        in_access_list=in_access_list,
        is_restricted_time=_is_restricted_time(start=start, end=end),
    )


def _is_restricted_time(*, start: dtm.datetime, end: dtm.datetime):
    """
    This function assumes that booking duration is less than 3 hours. Otherwise, returned flag may be wrong.
    """
    start = to_msk(start)
    end = to_msk(end)

    restricted_time_start = dtm.time(hour=8)
    restricted_time_end = dtm.time(hour=19)
    started_on_weekday = 0 <= start.date().weekday() <= 4
    ended_on_weekday = 0 <= end.date().weekday() <= 4

    if start.date() == end.date():
        if started_on_weekday:
            if start.time() <= end.time() <= restricted_time_start:
                return False
            if restricted_time_end <= start.time() <= end.time():
                return False
        else:
            return False
    else:
        if (not started_on_weekday or restricted_time_end <= start.time()) and (
            not ended_on_weekday or end.time() <= restricted_time_start
        ):
            return False
    return True


def check_rules(
    *,
    room: Room,
    booking_longer_than_3_hours: bool,
    highest_role: Role,
    in_access_list: bool,
    is_restricted_time: bool,
) -> tuple[bool, str]:
    # Только staff и students имеют доступ к бронированию
    if highest_role == "none":
        return False, "You must be a student or staff to book rooms (college students can't book rooms)."

    if room.id == "309A" and in_access_list and booking_longer_than_3_hours:
        return False, "309A can't be booked for more than 3 hours."

    # staff всегда имеет доступ к жёлтым и красным комнатам с неограниченной длиной брони
    if highest_role == "staff" and room.access_level in ["yellow", "red"]:
        return True, ""

    if highest_role == "staff" and in_access_list:
        return True, ""

    if highest_role == "staff":
        return False, "You don't have rights to book this room."

    # Студенты не могут бронировать комнаты больше чем на 3 часа
    if highest_role == "student" and booking_longer_than_3_hours:
        if in_access_list:
            return True, ""

        if room.access_level == "yellow":
            return False, "Students can't create booking for more than 3 hours."

    if in_access_list:
        return True, ""

    if highest_role == "student" and room.access_level == "red":
        return False, "Students can't book rooms with red access level."

    if room.access_level == "yellow" and not room.restrict_daytime:
        return True, ""

    if room.access_level == "yellow" and room.restrict_daytime:
        if is_restricted_time:
            return False, "Students can't book lecture rooms during working hours."
        else:
            return True, ""

    return False, "You don't have rights to book this room.."
