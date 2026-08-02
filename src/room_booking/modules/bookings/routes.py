"""
Lists of bookings for rooms.
"""
# ruff: noqa: B008

__all__ = ["router"]

import datetime as dtm
from typing import cast

import exchangelib
import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr

from src.inh_accounts_sdk import inh_accounts
from src.logging_ import logger
from src.room_booking.dependencies import ApiKeyDep, VerifiedDep, VerifiedOrApiKeyDep, VerifiedOrRoomTvDep
from src.room_booking.modules.bmp.repository import bmp_repository
from src.room_booking.modules.bookings.exchange_repository import exchange_booking_repository
from src.room_booking.modules.bookings.schemas import (
    Booking,
    CancelExtraBookingRequest,
    CreateBookingRequest,
    PatchBookingRequest,
)
from src.room_booking.modules.bookings.service import (
    apply_related_to_me,
    calendar_item_to_booking,
    get_emails_to_attendees_index,
    get_first_room_from_emails,
    set_related_to_me,
)
from src.room_booking.modules.bookings.tz_utils import msk_timezone
from src.room_booking.modules.rooms.repository import room_repository
from src.room_booking.modules.rules.service import can_book, can_use_recurrence


def _default_date_range(
    start: dtm.datetime | None,
    end: dtm.datetime | None,
) -> tuple[dtm.datetime, dtm.datetime]:
    now_msk = dtm.datetime.now(msk_timezone)
    today = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)
    if start is None:
        start = today - dtm.timedelta(days=7)
    if end is None:
        end = today + dtm.timedelta(days=14)
    return start, end


router = APIRouter(
    tags=["Bookings"],
    responses={
        403: {"description": "Unauthorized"},
        429: {"description": "EWS error, probably Outlook is down"},
    },
)


@router.get(
    "/bookings/",
    responses={400: {"description": "Start must be before end"}, 404: {"description": "Room not found"}},
)
async def bookings(
    auth: VerifiedOrApiKeyDep,
    room_id: str | None = Query(None, title="ID for getting single room bookings"),
    room_ids: list[str] | None = Query(None, title="IDs for multiple rooms bookings"),
    start: dtm.datetime | None = Query(
        None, description="Start date, if not provided, will be set to 7 days before current date"
    ),
    end: dtm.datetime | None = Query(
        None, description="End date, if not provided, will be set to 14 days after current date"
    ),
    include_red: bool = Query(False, description="Include red-access rooms bookings when getting all"),
) -> list[Booking]:
    """
    Get bookings for all or for specific rooms.

    - If `room_id` is provided, get bookings for that room.
    - If `room_ids` is provided, get bookings for specified rooms.
    - If neither `room_id` nor `room_ids` is provided, get bookings for all rooms.
    - If both `room_id` and `room_ids` are provided, get bookings for all specified rooms.

    `include_red` only applies when getting all rooms and is `False` be default.
    """

    start, end = _default_date_range(start, end)
    if start >= end:
        raise HTTPException(400, "Start must be before end")

    room_ids_to_fetch: list[str] = []

    if not room_ids and not room_id:  # nothing provided, get all rooms
        room_ids_to_fetch = [room.id for room in room_repository.get_all(include_red)]
    elif room_id and not room_ids:  # only room id is provided
        if room_repository.get_by_id(room_id) is None:
            raise HTTPException(404, "Room not found")
        room_ids_to_fetch = [room_id]
    elif room_id and room_ids:  # both room id and room ids are provided
        room_ids_to_fetch = [room_id, *room_ids] if room_id not in room_ids else room_ids
    elif room_ids:  # only room ids are provided
        room_ids_to_fetch = room_ids
    else:
        raise AssertionError("Invalid combination of room_id and room_ids, not even possible")

    bookings = await exchange_booking_repository.get_bookings_for_certain_rooms(
        room_ids=room_ids_to_fetch, from_dt=start, to_dt=end
    )
    return apply_related_to_me(bookings, auth)


@router.get("/bookings/my")
async def my_bookings(
    user: VerifiedDep,
    start: dtm.datetime | None = Query(
        None, description="Start date, if not provided, will be set to 7 days before current date"
    ),
    end: dtm.datetime | None = Query(
        None, description="End date, if not provided, will be set to 14 days after current date"
    ),
) -> list[Booking]:
    start, end = _default_date_range(start, end)
    if start >= end:
        raise HTTPException(400, "Start must be before end")
    bookings = await exchange_booking_repository.fetch_user_bookings(attendee_email=user.email, start=start, end=end)
    return set_related_to_me(bookings, user.email)


@router.post(
    "/bookings/",
    responses={
        400: {"description": "Start must be before end or invalid recurrence"},
        403: {"description": "Room declined the booking OR Invalid user OR Recurrence not allowed"},
        404: {
            "description": "Room not found OR Booking was removed during booking OR Room attendee not found in booking attendees"
        },
    },
)
async def create_booking(user: VerifiedDep, request: CreateBookingRequest) -> Booking:
    if request.start >= request.end:
        raise HTTPException(400, "Start must be before end")
    room = room_repository.get_by_id(room_id=request.room_id)
    if room is None:
        raise HTTPException(404, "Room not found")

    innohassle_user = await inh_accounts.get_user(innohassle_id=user.innohassle_id)

    if innohassle_user is None:
        raise HTTPException(403, "Invalid user")

    can, why = can_book(user=innohassle_user.innopolis_info, room=room, start=request.start, end=request.end)
    if not can:
        raise HTTPException(403, why)

    if request.recurrence is not None and not can_use_recurrence(
        email=innohassle_user.innopolis_info.email, user=innohassle_user
    ):
        raise HTTPException(403, "Recurrence is not allowed for your account")

    ews_recurrence = None
    if request.recurrence is not None:
        try:
            ews_recurrence = request.recurrence.to_exchangelib_recurrence()
        except ValueError as e:
            raise HTTPException(400, str(e))

    booking = await exchange_booking_repository.create_booking(
        room=room,
        start=request.start,
        end=request.end,
        title=request.title,
        organizer=innohassle_user,
        participant_emails=request.participant_emails or [],
        recurrence=ews_recurrence,
        categories=request.categories,
        description=request.description,
    )
    return set_related_to_me(booking, innohassle_user.innopolis_info.email)


class AttendeeDetails(BaseModel):
    name: str | None
    email: str | None
    telegram_username: str | None
    is_staff: bool
    is_student: bool
    is_college: bool


@router.get(
    "/bookings/{outlook_booking_id:path}/get-attendee-details",
    responses={400: {"description": "Invalid email"}, 404: {"description": "Booking not found OR details not found"}},
)
async def get_attendee_details(
    outlook_booking_id: str,
    user_email: EmailStr,
    auth: VerifiedOrRoomTvDep,
) -> AttendeeDetails:
    identification = auth.user.email if auth.user is not None else auth.room.resource_email if auth.room else None
    logger.info(f"{identification=} trying to get attendee details for {user_email} in booking {outlook_booking_id}")
    if not (user_email.endswith(("@innopolis.university", "@innopolis.ru"))):
        logger.warning(
            f"{identification=} trying to get attendee details for {user_email} in booking {outlook_booking_id} but email is not from Innopolis University"
        )
        raise HTTPException(400, "Invalid email")

    searched_user = await inh_accounts.get_user(email=user_email)

    if searched_user is None:
        raise HTTPException(404, "Details not found")

    return AttendeeDetails(
        name=searched_user.innopolis_info.name,
        email=searched_user.innopolis_info.email,
        telegram_username=searched_user.telegram_info.username if searched_user.telegram_info else None,
        is_staff=searched_user.innopolis_info.is_staff,
        is_student=searched_user.innopolis_info.is_student,
        is_college=searched_user.innopolis_info.is_college,
    )


@router.get(
    "/bookings/by-entry-id/{outlook_entry_id:path}",
    responses={404: {"description": "Booking not found OR Room attendee not found in booking attendees"}},
)
async def get_booking_by_entry_id(
    auth: VerifiedOrRoomTvDep,
    outlook_entry_id: str,
    room_id: str,
) -> Booking:
    room = room_repository.get_by_id(room_id=room_id)
    if room is None:
        raise HTTPException(404, "Room not found")

    booking = await exchange_booking_repository.get_booking_by_entry_id(
        outlook_entry_id=outlook_entry_id,
        room=room,
    )
    if booking is None:
        raise HTTPException(404, "Booking not found")

    if auth.user is not None:
        return set_related_to_me(booking, auth.user.email)
    return booking


@router.delete(
    "/bookings/by-entry-id/{outlook_entry_id:path}",
    status_code=200,
    responses={
        200: {"description": "Canceled successfully"},
        403: {"description": "You are not the participant of the booking"},
        404: {"description": "Booking not found OR Room not found"},
    },
)
async def delete_booking_by_entry_id(
    user: VerifiedDep,
    outlook_entry_id: str,
    room_id: str,
) -> None:
    room = room_repository.get_by_id(room_id=room_id)
    if room is None:
        raise HTTPException(404, "Room not found")

    calendar_item = await exchange_booking_repository.get_calendar_item_by_entry_id(
        outlook_entry_id=outlook_entry_id,
        room=room,
    )
    if calendar_item is None:
        raise HTTPException(404, "Booking not found")

    if user.email not in get_emails_to_attendees_index(calendar_item):
        raise HTTPException(403, "You are not the participant of the booking")

    canceled = await exchange_booking_repository.cancel_booking(calendar_item, email=user.email)
    if not canceled:
        raise HTTPException(404, "Booking not found")


@router.post(
    "/bookings/cancel-extra",
    status_code=200,
    responses={
        200: {"description": "Canceled successfully"},
        403: {"description": "You are not the participant of the booking"},
        404: {"description": "Booking not found OR Room not found"},
    },
)
async def cancel_extra_booking(user: VerifiedDep, request: CancelExtraBookingRequest) -> None:
    room = room_repository.get_by_id(room_id=request.room_id)
    if room is None:
        raise HTTPException(404, "Room not found")

    if request.outlook_booking_id:
        calendar_item = await exchange_booking_repository.get_booking(request.outlook_booking_id)
        if calendar_item is None:
            raise HTTPException(404, "Booking not found")
        if user.email not in get_emails_to_attendees_index(calendar_item):
            raise HTTPException(403, "You are not the participant of the booking")
        await exchange_booking_repository.cancel_booking(calendar_item, email=user.email)
        return

    if await bmp_repository.cancel_auto_booking_by_slot(
        room_id=request.room_id,
        start=request.start,
        end=request.end,
        title=request.title,
        email=user.email,
    ):
        return

    calendar_item: exchangelib.CalendarItem | None = None
    if request.outlook_entry_id:
        calendar_item = await exchange_booking_repository.get_calendar_item_by_entry_id(
            outlook_entry_id=request.outlook_entry_id,
            room=room,
        )

    if calendar_item is None:
        calendar_item = await exchange_booking_repository.find_calendar_item_for_room_slot(
            room=room,
            start=request.start,
            end=request.end,
            title=request.title,
        )

    if calendar_item is None:
        raise HTTPException(404, "Booking not found")

    if user.email not in get_emails_to_attendees_index(calendar_item):
        raise HTTPException(403, "You are not the participant of the booking")

    canceled = await exchange_booking_repository.cancel_booking(calendar_item, email=user.email)
    if not canceled:
        raise HTTPException(404, "Booking not found")


@router.get(
    "/bookings/{outlook_booking_id:path}",
    responses={404: {"description": "Booking not found OR Room attendee not found in booking attendees"}},
)
async def get_booking(outlook_booking_id: str, user: VerifiedDep) -> Booking:
    calendar_item = await exchange_booking_repository.get_booking(outlook_booking_id)
    if calendar_item is None:
        raise HTTPException(404, "Booking not found")

    if (booking := calendar_item_to_booking(calendar_item)) is None:
        raise HTTPException(404, "Room attendee not found in booking attendees")

    return set_related_to_me(booking, user.email)


@router.patch(
    "/bookings/{outlook_booking_id:path}",
    responses={
        400: {"description": "Invalid booking"},
        403: {"description": "You are not the participant of the booking OR Invalid user"},
        404: {"description": "Booking not found OR Room attendee not found in booking attendees"},
    },
)
async def update_booking(
    outlook_booking_id: str,
    user: VerifiedDep,
    request: PatchBookingRequest,
) -> Booking:
    booking = await exchange_booking_repository.get_booking(item_id=outlook_booking_id)

    if booking is None:
        raise HTTPException(404, "Booking not found")

    email_index = get_emails_to_attendees_index(booking)
    room = get_first_room_from_emails(email_index.keys())

    if user.email not in email_index:
        raise HTTPException(403, "You are not the participant of the booking")

    if room is None:
        raise HTTPException(400, "Invalid booking")

    innohassle_user = await inh_accounts.get_user(innohassle_id=user.innohassle_id)

    if innohassle_user is None:
        raise HTTPException(403, "Invalid user")

    can, why = can_book(
        user=innohassle_user.innopolis_info,
        room=room,
        start=cast(dtm.datetime, request.start or booking.start),
        end=cast(dtm.datetime, request.end or booking.end),
        is_update=True,
    )
    if not can:
        raise HTTPException(403, why)

    booking = await exchange_booking_repository.update_booking(
        item_id=outlook_booking_id,
        new_start=request.start,
        new_end=request.end,
        new_title=request.title,
    )

    if booking is None:
        raise HTTPException(404, "Booking not found after update")

    return set_related_to_me(booking, user.email)


@router.delete(
    "/bookings/{outlook_booking_id:path}",
    status_code=200,
    responses={
        200: {"description": "Deleted successfully"},
        403: {"description": "You are not the participant of the booking"},
        404: {"description": "Booking not found"},
    },
)
async def delete_booking(user: VerifiedDep, outlook_booking_id: str):
    booking = await exchange_booking_repository.get_booking(item_id=outlook_booking_id)
    if booking is None:
        raise HTTPException(404, "Booking not found")

    if user.email not in get_emails_to_attendees_index(booking):
        raise HTTPException(403, "You are not the participant of the booking")

    await exchange_booking_repository.cancel_booking(booking, email=user.email)


@router.get(
    "/user/{user_id}/bookings",
    responses={400: {"description": "Start must be before end"}, 404: {"description": "User not found"}},
)
async def get_user_bookings(
    user_id: str,
    _: ApiKeyDep,
    start: dtm.datetime | None = Query(
        None, description="Start date, if not provided, will be set to 7 days before current date"
    ),
    end: dtm.datetime | None = Query(
        None, description="End date, if not provided, will be set to 14 days after current date"
    ),
) -> list[Booking]:
    start, end = _default_date_range(start, end)
    if start >= end:
        raise HTTPException(400, "Start must be before end")

    try:
        innohassle_user = await inh_accounts.get_user(innohassle_id=user_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.json())

    if innohassle_user is None:
        raise HTTPException(404, "User not found")

    bookings = await exchange_booking_repository.fetch_user_bookings(
        attendee_email=innohassle_user.innopolis_info.email,
        start=start,
        end=end,
    )
    return set_related_to_me(bookings, innohassle_user.innopolis_info.email)
