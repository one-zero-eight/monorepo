import datetime as dtm

from fastapi import APIRouter
from fastapi.security import HTTPBearer

from src.schedule_assistant.dependencies import VerifyTokenDep
from src.schedule_assistant.modules.bookings.client import BookingDTO, RoomDTO, booking_client
from src.schedule_assistant.utcnow import utcnow

security = HTTPBearer()

router = APIRouter(tags=["Bookings"])


@router.get("/dev/bookings")
async def get_all_bookings(
    _user_and_token: VerifyTokenDep,
) -> list[BookingDTO]:
    _now = utcnow()
    return await booking_client.get_all_bookings(
        _now,
        _now + dtm.timedelta(days=30),
    )


@router.get("/dev/bookings/{room_id}")
async def get_bookings(
    room_id: str,
    _user_and_token: VerifyTokenDep,
) -> list[BookingDTO]:
    _now = utcnow()
    return await booking_client.get_room_bookings(
        room_id,
        _now,
        _now + dtm.timedelta(days=30),
    )


@router.get("/dev/rooms")
async def get_rooms(_user_and_token: VerifyTokenDep) -> list[RoomDTO]:
    return await booking_client.get_rooms()
