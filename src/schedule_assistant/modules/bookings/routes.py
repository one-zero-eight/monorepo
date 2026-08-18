from fastapi import APIRouter

from src.schedule_assistant.dependencies import ModeratorDep
from src.schedule_assistant.modules.bookings import service
from src.schedule_assistant.modules.bookings.schemas import (
    BatchBookRequest,
    BookingReview,
    BookingTask,
    CancelExtraRequest,
)

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.get("/review")
async def get_booking_review(_moderator: ModeratorDep) -> BookingReview:
    return await service.get_booking_review()


@router.get("/tasks/{task_id}")
async def get_booking_task(_moderator: ModeratorDep, task_id: str) -> BookingTask:
    return service.get_booking_task(task_id)


@router.post("/batch")
async def batch_book_slots(_moderator: ModeratorDep, request: BatchBookRequest) -> BookingTask:
    return service.start_batch_book(request)


@router.post("/cancel-extra")
async def cancel_extra_bookings(_moderator: ModeratorDep, request: CancelExtraRequest) -> BookingTask:
    return service.start_cancel_extra(request)
