from typing import Annotated

from fastapi import APIRouter, Query

from src.schedule_assistant.dependencies import ModeratorDep, ScheduleConfigRepoDep
from src.schedule_assistant.modules.bookings import service
from src.schedule_assistant.modules.bookings.schemas import (
    BatchBookRequest,
    BookingReview,
    BookingTask,
    CancelBookingRequest,
    CancelExtraRequest,
)

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.get("/review")
async def get_booking_review(_moderator: ModeratorDep, config_repo: ScheduleConfigRepoDep) -> BookingReview:
    return await service.get_booking_review(config_repo)


@router.get("/tasks")
async def list_booking_tasks(
    _moderator: ModeratorDep, limit: Annotated[int, Query(ge=1, le=100)] = 100, offset: Annotated[int, Query(ge=0)] = 0
) -> list[BookingTask]:
    return service.list_tasks(limit=limit, offset=offset)


@router.post("/tasks/{task_id}/reconcile")
async def reconcile_booking_task(_moderator: ModeratorDep, task_id: str) -> BookingTask:
    return await service.reconcile_booking_task(task_id)


@router.post("/cancel")
async def cancel_bookings(
    _moderator: ModeratorDep, request: CancelBookingRequest, config_repo: ScheduleConfigRepoDep
) -> BookingTask:
    return await service.start_cancel_booking(config_repo, request)


@router.get("/tasks/{task_id}")
async def get_booking_task(_moderator: ModeratorDep, task_id: str) -> BookingTask:
    return service.get_booking_task(task_id)


@router.post("/batch")
async def batch_book_slots(
    _moderator: ModeratorDep, request: BatchBookRequest, config_repo: ScheduleConfigRepoDep
) -> BookingTask:
    return await service.start_batch_book(config_repo, request)


@router.post("/cancel-extra")
async def cancel_extra_bookings(
    _moderator: ModeratorDep, request: CancelExtraRequest, config_repo: ScheduleConfigRepoDep
) -> BookingTask:
    return await service.start_cancel_extra(config_repo, request)
