from fastapi import APIRouter

from src.schedule_assistant.dependencies import ModeratorDep
from src.schedule_assistant.modules.bookings import service
from src.schedule_assistant.modules.bookings.schemas import (
    BatchBookRequest,
    BatchBookResponse,
    BookingReview,
    CancelExtraRequest,
    CancelExtraResponse,
)

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.get("/review")
async def get_booking_review(_moderator: ModeratorDep) -> BookingReview:
    return await service.get_booking_review()


@router.post("/batch")
async def batch_book_slots(_moderator: ModeratorDep, request: BatchBookRequest) -> BatchBookResponse:
    return await service.batch_book_slots(request)


@router.post("/cancel-extra")
async def cancel_extra_bookings(_moderator: ModeratorDep, request: CancelExtraRequest) -> CancelExtraResponse:
    return await service.cancel_extra_bookings(request)
