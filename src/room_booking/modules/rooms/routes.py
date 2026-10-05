"""
Routes for the rooms information.
"""

__all__ = ["router"]

import datetime as dtm

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.inh_accounts_sdk import inh_accounts
from src.room_booking.config_schema import AccessToRoom, Room
from src.room_booking.dependencies import VerifiedDep, VerifiedOrApiKeyDep, VerifiedOrApiKeyOrRoomTvDep
from src.room_booking.modules.bookings.exchange_repository import Booking, exchange_booking_repository
from src.room_booking.modules.bookings.service import apply_related_to_me
from src.room_booking.modules.rooms.repository import room_repository
from src.room_booking.modules.rules.service import can_book

router = APIRouter(tags=["Rooms"])


class CanBookResponse(BaseModel):
    can_book: bool
    reason_why_cannot: str


@router.get("/rooms/")
async def rooms(_: VerifiedOrApiKeyDep, include_red: bool = False) -> list[Room]:
    return room_repository.get_all(include_red)


@router.get(
    "/rooms/my-access-list",
    responses={
        200: {"description": "Rooms with special access"},
    },
)
async def my_access_list(user: VerifiedDep) -> list[Room]:
    """
    Get rooms that the user has special access to (f.e. 309A or 108 lecture room).
    """
    room_ids = list(room_repository.get_access_list_for_user(user.email).keys())
    rooms = room_repository.get_by_ids(room_ids)
    rooms = list(filter(None, rooms))
    return rooms


@router.get("/rooms/all-access-lists", responses={200: {"description": "All access lists"}})
async def all_access_lists(user: VerifiedDep) -> dict[str, list[AccessToRoom]]:
    innohassle_user = await inh_accounts.get_user(innohassle_id=user.innohassle_id)
    if innohassle_user is None:
        raise HTTPException(404, "User not found")
    if not innohassle_user.innohassle_admin:
        raise HTTPException(403, "User is not an admin")
    return room_repository.access_lists


@router.get(
    "/room/{id}",
    responses={
        200: {"description": "Room info"},
        404: {"description": "Room not found"},
    },
)
async def room_route(id: str, _: VerifiedDep) -> Room:
    room = room_repository.get_by_id(id)
    if room is None:
        raise HTTPException(404, "Room not found")
    return room


@router.get(
    "/room/{id}/can-book",
    responses={
        200: {"description": "Can book"},
        400: {"description": "Start must be before end"},
        403: {"description": "Invalid user"},
        404: {"description": "Room not found"},
    },
)
async def room_can_book_route(
    id: str, user: VerifiedDep, start: dtm.datetime, end: dtm.datetime, is_update: bool = False
) -> CanBookResponse:
    """
    Check if the user can book a room for the given time range.
    """
    room = room_repository.get_by_id(id)
    if room is None:
        raise HTTPException(404, "Room not found")
    innohassle_user = await inh_accounts.get_user(innohassle_id=user.innohassle_id)

    if innohassle_user is None:
        raise HTTPException(403, "Invalid user")

    can, reason = can_book(user=innohassle_user.innopolis_info, room=room, start=start, end=end, is_update=is_update)
    return CanBookResponse(can_book=can, reason_why_cannot=reason)


@router.get(
    "/room/{id}/bookings",
    responses={
        200: {"description": "Room bookings"},
        400: {"description": "Start must be before end"},
        404: {"description": "Room not found"},
    },
)
async def room_bookings_route(
    id: str, auth: VerifiedOrApiKeyOrRoomTvDep, start: dtm.datetime, end: dtm.datetime
) -> list[Booking]:
    if start >= end:
        raise HTTPException(400, "Start must be before end")
    obj = room_repository.get_by_id(id)
    if obj is None:
        raise HTTPException(404, "Room not found")
    bookings = await exchange_booking_repository.get_bookings_for_room(room_id=id, from_dt=start, to_dt=end)
    return apply_related_to_me(bookings, auth)
