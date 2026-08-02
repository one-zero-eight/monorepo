# ruff: noqa: BLE001, B008
import datetime as dtm
import time as tm

from exchangelib.recurrence import Recurrence
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from src.logging_ import logger
from src.room_booking.dependencies import ApiKeyDep
from src.room_booking.modules.bmp.repository import (
    BmpBatchCreateEntry,
    BmpBatchItemResult,
    CancelAllAutoBookingsResult,
    bmp_repository,
)
from src.room_booking.modules.bookings.schemas import Booking, CreateBookingRequest
from src.room_booking.modules.bookings.tz_utils import msk_timezone
from src.room_booking.modules.rooms.repository import room_repository

router = APIRouter(
    tags=["BMP Specialist"],
    prefix="/bmp",
    responses={
        401: {"description": "Unable to verify credentials OR Credentials not provided"},
        403: {"description": "Room declined the booking OR Recurrence not allowed"},
        404: {
            "description": "Booking or calendar item not found (unknown id, already cancelled, or not a calendar item)"
        },
        429: {"description": "EWS error, probably Outlook is down"},
    },
)


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


class BmpBatchRequest(BaseModel):
    bookings: list[CreateBookingRequest]


class BmpBatchCancelRequest(BaseModel):
    outlook_booking_ids: list[str]


def _parse_bmp_batch_entry(request: CreateBookingRequest) -> BmpBatchCreateEntry:
    if request.start >= request.end:
        raise HTTPException(400, "Start must be before end")
    room = room_repository.get_by_id(request.room_id)
    if room is None:
        raise HTTPException(404, "Room not found")
    ews_recurrence: Recurrence | None = None
    if request.recurrence is not None:
        try:
            ews_recurrence = request.recurrence.to_exchangelib_recurrence()
        except ValueError as e:
            raise HTTPException(400, str(e))
    return BmpBatchCreateEntry(
        room=room,
        start=request.start,
        end=request.end,
        title=request.title,
        participant_emails=request.participant_emails or [],
        recurrence=ews_recurrence,
        categories=request.categories,
        description=request.description,
    )


async def _create_bmp_booking(request: CreateBookingRequest) -> Booking:
    entry = _parse_bmp_batch_entry(request)
    return await bmp_repository.create_booking(
        room=entry.room,
        start=entry.start,
        end=entry.end,
        title=entry.title,
        participant_emails=entry.participant_emails,
        recurrence=entry.recurrence,
        categories=entry.categories,
        description=entry.description,
    )


@router.get("/auto-bookings/")
async def list_auto_bookings(
    _: ApiKeyDep,
    start: dtm.datetime | None = Query(None),
    end: dtm.datetime | None = Query(None),
) -> list[Booking]:
    start, end = _default_date_range(start, end)
    if start >= end:
        raise HTTPException(400, "Start must be before end")
    return await bmp_repository.list_auto_bookings(start, end)


@router.get(
    "/items/{item_id:path}",
    response_class=PlainTextResponse,
    responses={404: {"description": "Item not found"}},
)
async def get_bmp_item_test(
    _: ApiKeyDep,
    item_id: str,
) -> PlainTextResponse:
    item = await bmp_repository.get_item(item_id)
    if item is None:
        raise HTTPException(404, "Item not found")
    return PlainTextResponse(str(item))


@router.get(
    "/auto-bookings/{outlook_booking_id:path}",
    responses={404: {"description": "Booking not found"}},
)
async def get_auto_booking(
    _: ApiKeyDep,
    outlook_booking_id: str,
) -> Booking:
    calendar_item = await bmp_repository.get_booking(outlook_booking_id)
    if calendar_item is None:
        raise HTTPException(404, "Booking not found")
    if booking := bmp_repository.booking_from_calendar_item(calendar_item):
        return booking
    raise HTTPException(404, "Booking not found")


@router.delete("/auto-bookings/")
async def cancel_all_auto_bookings(
    _: ApiKeyDep,
) -> CancelAllAutoBookingsResult:
    return await bmp_repository.cancel_all_auto_bookings()


@router.delete("/auto-bookings/batch")
async def batch_cancel_auto_bookings(
    _: ApiKeyDep,
    request: BmpBatchCancelRequest,
) -> CancelAllAutoBookingsResult:
    actor_email = bmp_repository.account_email
    t_route = tm.monotonic()
    logger.info(f"BMP batch cancel auto bookings started: user={actor_email} count={len(request.outlook_booking_ids)}")
    result = await bmp_repository.cancel_bookings_batch(
        request.outlook_booking_ids,
        email=actor_email,
    )
    logger.info(
        f"BMP batch cancel auto bookings finished: user={actor_email} "
        f"cancelled={len(result.cancelled)} failed={len(result.failed)} "
        f"took {tm.monotonic() - t_route:.3f}s"
    )
    return result


@router.delete(
    "/auto-bookings/{outlook_booking_id:path}",
    responses={404: {"description": "Booking not found"}},
)
async def delete_auto_booking(
    _: ApiKeyDep,
    outlook_booking_id: str,
) -> None:
    calendar_item = await bmp_repository.get_booking(outlook_booking_id)
    if calendar_item is None:
        raise HTTPException(404, "Booking not found")
    await bmp_repository.cancel_booking(calendar_item, email=bmp_repository.account_email)


@router.post(
    "/auto-bookings/",
    responses={
        400: {"description": "Start must be before end or invalid recurrence"},
        403: {"description": "Room declined the booking OR Recurrence not allowed"},
        404: {"description": "Room not found, booking was removed, or room attendee not found"},
    },
)
async def create_auto_booking(
    _: ApiKeyDep,
    request: CreateBookingRequest,
) -> Booking:
    return await _create_bmp_booking(request)


@router.post("/auto-bookings/batch")
async def batch_auto_bookings(
    _: ApiKeyDep,
    request: BmpBatchRequest,
) -> dict[str, BmpBatchItemResult]:
    actor_email = bmp_repository.account_email
    t_route = tm.monotonic()
    logger.info(f"BMP batch auto bookings started: user={actor_email} count={len(request.bookings)}")
    result: dict[str, BmpBatchItemResult] = {}
    pending_keys: list[str] = []
    pending_entries: list[BmpBatchCreateEntry] = []

    for i, req in enumerate(request.bookings):
        key = str(i)
        try:
            pending_entries.append(_parse_bmp_batch_entry(req))
            pending_keys.append(key)
        except HTTPException as e:
            error: str | None
            message_body: str | None = None
            if isinstance(e.detail, dict):
                error = e.detail.get("message")
                if error is not None:
                    error = str(error)
                message_body = e.detail.get("message_body")
                if message_body is not None:
                    message_body = str(message_body)
            else:
                error = e.detail if isinstance(e.detail, str) else str(e.detail)
            result[key] = BmpBatchItemResult(
                status="error",
                booking=None,
                error=error,
                message_body=message_body,
            )
        except Exception as e:
            logger.exception(f"Error creating BMP booking: {e}")
            result[key] = BmpBatchItemResult(status="error", booking=None, error=str(e))

    if pending_entries:
        outcomes = await bmp_repository.create_bookings_batch(pending_entries)
        for key, outcome in zip(pending_keys, outcomes, strict=True):
            result[key] = outcome

    ok = sum(1 for o in result.values() if o.status == "ok")
    err = len(result) - ok
    logger.info(
        f"BMP batch auto bookings finished: user={actor_email} ok={ok} error={err} took {tm.monotonic() - t_route:.3f}s"
    )
    return result
