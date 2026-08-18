import datetime as dtm

import httpx
from fastapi import HTTPException, status

from src.logging_ import logger
from src.schedule_assistant.modules.bookings.client import booking_client
from src.schedule_assistant.modules.bookings.review import (
    ReviewIndex,
    build_review_index,
    collect_booking_payloads,
)
from src.schedule_assistant.modules.bookings.schemas import (
    BatchBookItemResult,
    BatchBookRequest,
    BatchBookResponse,
    BookingReview,
    CancelExtraRequest,
    CancelExtraResponse,
)
from src.schedule_assistant.modules.issues.booking_slots import build_bookable_slots
from src.schedule_assistant.modules.issues.booking_window import resolve_booking_fetch_window
from src.schedule_assistant.modules.schedule_config.repository import schedule_config_repository
from src.schedule_assistant.modules.schedule_config.schemas import TermConfig


def _require_term() -> TermConfig:
    term = schedule_config_repository.get_term()
    if term is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule term config is required for booking review",
        )
    return term


def _booking_window(term: TermConfig) -> tuple[dtm.datetime, dtm.datetime] | None:
    return resolve_booking_fetch_window(term.semester.start_date, term.semester.end_date)


async def _load_review_index() -> ReviewIndex:
    term = _require_term()
    sections = schedule_config_repository.get_sections()
    courses = schedule_config_repository.get_courses()
    config_rooms = schedule_config_repository.get_rooms()
    known_room_ids = {room.id for room in config_rooms.rooms}
    try:
        booking_rooms = await booking_client.get_rooms()
        known_room_ids.update(room.id for room in booking_rooms)
    except httpx.HTTPError as error:
        logger.warning(f"Failed to load booking rooms: {error}")

    slots = build_bookable_slots(courses, sections, term, known_room_ids)
    window = _booking_window(term)
    if window is None:
        return build_review_index(slots, auto_bookings=[], existing_bookings=[])

    start, end = window
    try:
        existing_bookings = await booking_client.get_all_bookings(start, end)
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to load room bookings: {error}",
        ) from error
    try:
        auto_bookings = await booking_client.get_auto_bookings(start, end)
    except httpx.HTTPError as error:
        logger.warning(f"Failed to load auto-bookings: {error}")
        auto_bookings = []

    return build_review_index(slots, auto_bookings=auto_bookings, existing_bookings=existing_bookings)


async def get_booking_review() -> BookingReview:
    index = await _load_review_index()
    return index.tree


async def batch_book_slots(request: BatchBookRequest) -> BatchBookResponse:
    if not request.slot_ids:
        return BatchBookResponse(submitted=0, results=[])
    index = await _load_review_index()
    payloads = collect_booking_payloads(index, request.slot_ids, request.conflict_modes)
    if not payloads:
        return BatchBookResponse(submitted=0, results=[])
    try:
        raw_results = await booking_client.create_auto_bookings_batch(payloads)
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create auto-bookings: {error}",
        ) from error

    results: list[BatchBookItemResult] = []
    for index_key, payload in enumerate(payloads):
        item = raw_results.get(str(index_key))
        results.append(
            BatchBookItemResult(
                index=str(index_key),
                status=item.status if item is not None else "error",
                title=str(payload.get("title") or None),
                error=item.error if item is not None else "missing batch result",
            )
        )
    return BatchBookResponse(submitted=len(payloads), results=results)


async def cancel_extra_bookings(request: CancelExtraRequest) -> CancelExtraResponse:
    if not request.extra_ids:
        return CancelExtraResponse(cancelled=[], failed={})
    index = await _load_review_index()
    bmp_ids: list[str] = []
    bmp_id_to_extra: dict[str, str] = {}
    slot_targets: list[tuple[str, dict]] = []
    failed: dict[str, str] = {}
    cancelled: list[str] = []

    for extra_id in request.extra_ids:
        booking = index.extras.get(extra_id)
        if booking is None:
            failed[extra_id] = "unknown extra booking"
            continue
        outlook_booking_id = booking.get("outlook_booking_id")
        if outlook_booking_id:
            bmp_ids.append(str(outlook_booking_id))
            bmp_id_to_extra[str(outlook_booking_id)] = extra_id
            continue
        slot_targets.append((extra_id, booking))

    if bmp_ids:
        try:
            result = await booking_client.cancel_auto_bookings_batch(bmp_ids)
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to cancel auto-bookings: {error}",
            ) from error
        cancelled.extend(bmp_id_to_extra.get(item_id, item_id) for item_id in result.cancelled)
        for item_id, error in result.failed.items():
            failed[bmp_id_to_extra.get(item_id, item_id)] = error

    for extra_id, booking in slot_targets:
        try:
            await booking_client.cancel_extra_booking(
                room_id=str(booking.get("room_id") or ""),
                start=str(booking.get("start") or ""),
                end=str(booking.get("end") or ""),
                title=str(booking.get("title") or ""),
                outlook_booking_id=booking.get("outlook_booking_id"),
                outlook_entry_id=booking.get("outlook_entry_id"),
            )
            cancelled.append(extra_id)
        except httpx.HTTPError as error:
            failed[extra_id] = str(error)

    return CancelExtraResponse(cancelled=cancelled, failed=failed)
