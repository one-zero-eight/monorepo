import asyncio
import datetime as dtm
from collections.abc import Coroutine
from typing import Any, Literal

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
    BatchBookRequest,
    BookingReview,
    BookingTask,
    BookingTaskItem,
    CancelExtraRequest,
)
from src.schedule_assistant.modules.bookings.tasks import (
    book_result_from_items,
    cancel_result_from_items,
    create_task,
    get_task,
    save_task,
)
from src.schedule_assistant.modules.issues.booking_slots import build_bookable_slots
from src.schedule_assistant.modules.issues.booking_window import resolve_booking_fetch_window
from src.schedule_assistant.modules.schedule_config.repository import schedule_config_repository
from src.schedule_assistant.modules.schedule_config.schemas import TermConfig

TASK_TIMEOUT_SECONDS = 600
_background_tasks: set[asyncio.Task[None]] = set()


def _spawn(coro: Coroutine[Any, Any, None]) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


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


def get_booking_task(task_id: str) -> BookingTask:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking task not found")
    return task


def start_batch_book(request: BatchBookRequest) -> BookingTask:
    task = create_task(kind="book", items=[], current="Готовим слоты…")
    _spawn(_run_book_task(task.task_id, request))
    return task


def start_cancel_extra(request: CancelExtraRequest) -> BookingTask:
    task = create_task(kind="cancel", items=[], current="Готовим отмену…")
    _spawn(_run_cancel_task(task.task_id, request))
    return task


def _items_by_index(task: BookingTask) -> dict[str, BookingTaskItem]:
    return {item.index: item for item in task.items}


def _finish_item(
    task: BookingTask, item: BookingTaskItem, *, status: Literal["ok", "error"], error: str | None
) -> None:
    if item.status not in {"ok", "error"}:
        task.done += 1
    item.status = status
    item.error = error
    task.current = item.title


async def _run_book_task(task_id: str, request: BatchBookRequest) -> None:
    task = get_task(task_id)
    if task is None:
        return
    task.status = "running"
    save_task(task)
    try:
        await asyncio.wait_for(_book_task_body(task_id, request), timeout=TASK_TIMEOUT_SECONDS)
    except HTTPException as error:
        task = get_task(task_id)
        if task is None:
            return
        task.status = "error"
        task.error = str(error.detail)
        task.book = book_result_from_items(task.items)
        save_task(task)
    except TimeoutError:
        task = get_task(task_id)
        if task is None or task.status in {"done", "error"}:
            return
        task.status = "error"
        task.error = "Booking task timed out"
        task.book = book_result_from_items(task.items)
        save_task(task)
    except Exception as error:  # noqa: BLE001
        logger.exception("Booking task failed")
        task = get_task(task_id)
        if task is None:
            return
        task.status = "error"
        task.error = str(error)
        task.book = book_result_from_items(task.items)
        save_task(task)


async def _book_task_body(task_id: str, request: BatchBookRequest) -> None:
    task = get_task(task_id)
    if task is None:
        return
    if not request.slot_ids:
        task.status = "done"
        task.book = book_result_from_items([])
        save_task(task)
        return

    index = await _load_review_index()
    payloads = collect_booking_payloads(index, request.slot_ids, request.conflict_modes)
    task = get_task(task_id)
    if task is None:
        return
    task.items = [
        BookingTaskItem(index=str(i), title=str(payload.get("title") or None), status="pending")
        for i, payload in enumerate(payloads)
    ]
    task.total = len(task.items)
    task.current = "Отправляем в Outlook…" if task.items else "Нет слотов для бронирования"
    save_task(task)
    if not payloads:
        task.status = "done"
        task.book = book_result_from_items([])
        save_task(task)
        return

    sent_ids: set[str] = set()
    by_index = _items_by_index(task)
    async for event in booking_client.stream_auto_bookings_batch(payloads):
        if event.event == "sent":
            for event_index in event.indexes or []:
                sent_ids.add(event_index)
                item = by_index.get(event_index)
                if item is not None and item.status == "pending":
                    item.status = "sent"
                    task.current = item.title
            task.sent = len(sent_ids)
        elif event.event == "item" and event.index is not None:
            item = by_index.get(event.index)
            if item is not None:
                if event.title:
                    item.title = event.title
                _finish_item(
                    task,
                    item,
                    status=event.status or "error",
                    error=event.error,
                )
        elif event.event == "done":
            break
        save_task(task)

    for item in task.items:
        if item.status not in {"ok", "error"}:
            _finish_item(task, item, status="error", error="missing batch result")
    task.status = "done"
    task.book = book_result_from_items(task.items)
    save_task(task)


async def _run_cancel_task(task_id: str, request: CancelExtraRequest) -> None:
    task = get_task(task_id)
    if task is None:
        return
    task.status = "running"
    save_task(task)
    try:
        await asyncio.wait_for(_cancel_task_body(task_id, request), timeout=TASK_TIMEOUT_SECONDS)
    except TimeoutError:
        task = get_task(task_id)
        if task is None or task.status in {"done", "error"}:
            return
        task.status = "error"
        task.error = "Cancel task timed out"
        task.cancel = cancel_result_from_items(task.items)
        save_task(task)
    except Exception as error:  # noqa: BLE001
        logger.exception("Cancel extra task failed")
        task = get_task(task_id)
        if task is None:
            return
        task.status = "error"
        task.error = str(error)
        task.cancel = cancel_result_from_items(task.items)
        save_task(task)


async def _cancel_task_body(task_id: str, request: CancelExtraRequest) -> None:
    task = get_task(task_id)
    if task is None:
        return
    if not request.extra_ids:
        task.status = "done"
        task.cancel = cancel_result_from_items([])
        save_task(task)
        return

    index = await _load_review_index()
    task = get_task(task_id)
    if task is None:
        return
    items: list[BookingTaskItem] = []
    for extra_id in request.extra_ids:
        booking = index.extras.get(extra_id)
        if booking is None:
            items.append(
                BookingTaskItem(
                    index=extra_id,
                    title=extra_id,
                    status="error",
                    error="unknown extra booking",
                )
            )
            continue
        items.append(
            BookingTaskItem(
                index=extra_id,
                title=str(booking.get("title") or extra_id),
                status="pending",
            )
        )
    task.items = items
    task.total = len(task.items)
    task.done = sum(1 for item in task.items if item.status == "error")
    save_task(task)

    by_index = _items_by_index(task)
    for extra_id in request.extra_ids:
        item = by_index[extra_id]
        if item.status == "error":
            continue
        booking = index.extras[extra_id]
        try:
            outlook_booking_id = booking.get("outlook_booking_id")
            if outlook_booking_id:
                await booking_client.cancel_auto_booking(str(outlook_booking_id))
            else:
                await booking_client.cancel_extra_booking(
                    room_id=str(booking.get("room_id") or ""),
                    start=str(booking.get("start") or ""),
                    end=str(booking.get("end") or ""),
                    title=str(booking.get("title") or ""),
                    outlook_booking_id=booking.get("outlook_booking_id"),
                    outlook_entry_id=booking.get("outlook_entry_id"),
                )
            _finish_item(task, item, status="ok", error=None)
        except httpx.HTTPError as error:
            _finish_item(task, item, status="error", error=str(error))
        save_task(task)

    task.status = "done"
    task.cancel = cancel_result_from_items(task.items)
    save_task(task)
