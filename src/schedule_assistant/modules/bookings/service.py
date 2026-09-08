import asyncio
import datetime as dtm
from collections.abc import Coroutine
from typing import Any, Literal

import httpx
from fastapi import HTTPException, status

from src.logging_ import logger
from src.schedule_assistant.modules.bookings.client import BmpStreamEventKind, booking_client
from src.schedule_assistant.modules.bookings.match import iter_booking_occurrences, iter_payload_occurrences
from src.schedule_assistant.modules.bookings.review import ReviewIndex, build_review_index, collect_booking_payloads
from src.schedule_assistant.modules.bookings.schemas import (
    BatchBookRequest,
    BookingEvidence,
    BookingOutcome,
    BookingReview,
    BookingTask,
    BookingTaskItem,
    BookingTaskItemStatus,
    BookingTaskKind,
    BookingTaskStatus,
    CancelBookingRequest,
    CancelExtraRequest,
    ReviewKind,
)
from src.schedule_assistant.modules.bookings.tasks import (
    ReservationConflictError,
    book_result_from_items,
    cancel_result_from_items,
    create_task,
    get_operation,
    get_task,
    list_operations,
    list_tasks,
    payload_key,
    save_task,
    task_lock,
)
from src.schedule_assistant.modules.issues.booking_slots import build_bookable_slots
from src.schedule_assistant.modules.issues.booking_window import resolve_booking_fetch_window
from src.schedule_assistant.modules.schedule_config.repository import schedule_config_repository
from src.schedule_assistant.modules.schedule_config.schemas import TermConfig
from src.schedule_assistant.utcnow import utcnow

TASK_TIMEOUT_SECONDS = 3600
_background_tasks: set[asyncio.Task[None]] = set()


def _spawn(coro: Coroutine[Any, Any, None]) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def stop_background_tasks() -> None:
    tasks = list(_background_tasks)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def _require_term() -> TermConfig:
    term = schedule_config_repository.get_term()
    if term is None:
        raise HTTPException(status_code=404, detail="Schedule term config is required for booking review")
    return term


def _booking_window(term: TermConfig) -> tuple[dtm.datetime, dtm.datetime] | None:
    from src.schedule_assistant.modules.schedule_config.semester_windows import union_semester_window

    window = union_semester_window(term)
    return resolve_booking_fetch_window(window.start_date, window.end_date)


async def _load_review_index() -> ReviewIndex:
    term = _require_term()
    sections = schedule_config_repository.get_sections()
    courses = schedule_config_repository.get_courses()
    config_rooms = schedule_config_repository.get_rooms()
    try:
        rooms = await booking_client.get_rooms()
        known_room_ids = {room.id for room in config_rooms.rooms} | {room.id for room in rooms}
        slots = build_bookable_slots(courses, sections, term, known_room_ids)
        window = _booking_window(term)
        if window is None:
            index = build_review_index(slots, auto_bookings=[], existing_bookings=[])
            for reviewed in index.slots.values():
                reviewed.review_kind = ReviewKind.UNKNOWN
            for program in index.tree.programs:
                for course in program.courses:
                    for component in course.components:
                        for slot in component.slots:
                            slot.review_kind = ReviewKind.UNKNOWN
                            slot.bookable = False
                            slot.disabled_reason = "Outside the checked booking window"
            return index
        start, end = window
        existing_bookings = await booking_client.get_all_bookings(start, end)
        auto_bookings = await booking_client.get_auto_bookings(start, end)
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to load booking evidence: {error}"
        ) from error
    index = build_review_index(slots, auto_bookings=auto_bookings, existing_bookings=existing_bookings)
    for extra in index.tree.extra_auto_bookings:
        evidence = BookingEvidence.model_validate(index.extras[extra.extra_id])
        for field in BookingEvidence.model_fields:
            setattr(extra, field, getattr(evidence, field))
        extra.can_cancel = bool(evidence.can_cancel and extra.outlook_booking_id and extra.organizer_mailbox)
    _overlay_operations(index)
    return index


def _overlay_operations(index: ReviewIndex) -> None:
    """A missing calendar entry must not erase a durable pending/uncertain intent."""
    by_slot: dict[str, list[BookingTaskItem]] = {}
    operations = [item for item in list_operations() if item.cancellation_scope is None]
    for operation in operations:
        reserved_occurrences = list(iter_payload_occurrences(operation.payload))
        for slot_id, reviewed in index.slots.items():
            own_slot = slot_id in operation.slot_ids
            overlaps = operation.room_id == reviewed.slot.payload.get("room_id") and any(
                start < reserved_end and reserved_start < end
                for start, end in iter_payload_occurrences(reviewed.slot.payload)
                for reserved_start, reserved_end in reserved_occurrences
            )
            if own_slot or overlaps:
                by_slot.setdefault(slot_id, []).append(operation)
    for program in index.tree.programs:
        for course in program.courses:
            for component in course.components:
                for slot in component.slots:
                    operations = by_slot.get(slot.slot_id, [])
                    if not operations:
                        continue
                    outcomes = {item.outcome for item in operations}
                    if BookingOutcome.CANCEL_REQUESTED in outcomes:
                        kind = ReviewKind.CANCELLING
                    elif BookingOutcome.UNKNOWN in outcomes or BookingOutcome.SUBMITTED in outcomes:
                        kind = ReviewKind.UNKNOWN
                    elif BookingOutcome.DECLINED in outcomes:
                        kind = ReviewKind.DECLINED
                    elif BookingOutcome.PENDING_APPROVAL in outcomes:
                        kind = ReviewKind.PENDING_APPROVAL
                    else:
                        # Only review's full occurrence coverage can establish BOOKED.
                        kind = slot.review_kind if slot.review_kind == ReviewKind.BOOKED else ReviewKind.UNKNOWN
                    slot.review_kind = kind
                    index.slots[slot.slot_id].review_kind = kind
                    item = max(operations, key=lambda item: item.checked_at or dtm.datetime.min.replace(tzinfo=dtm.UTC))
                    slot.room_response = item.room_response or "Unknown"
                    slot.room_presence = item.room_presence
                    slot.checked_at = item.checked_at
                    slot.message_body = item.message_body
                    slot.booking_ids = list(
                        dict.fromkeys(
                            [
                                *slot.booking_ids,
                                *[item.outlook_booking_id for item in operations if item.outlook_booking_id],
                            ]
                        )
                    )
                    slot.can_cancel = any(item.can_cancel for item in operations)


async def get_booking_review() -> BookingReview:
    return (await _load_review_index()).tree


def get_booking_task(task_id: str) -> BookingTask:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Booking task not found")
    return task


def _reserve(kind: BookingTaskKind, items: list[BookingTaskItem]) -> tuple[BookingTask, bool]:
    try:
        return create_task(kind=kind, items=items), True
    except ReservationConflictError as error:
        if len(error.task_ids) == 1:
            existing = get_booking_task(error.task_ids[0])
            if {payload_key(item.payload) for item in existing.items} == {payload_key(item.payload) for item in items}:
                return existing, False
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Some bookings already have reserved operations; reconcile them before retrying",
                "task_ids": error.task_ids,
            },
        ) from error


async def start_batch_book(request: BatchBookRequest) -> BookingTask:
    # Recover the server-side task even when review now blocks the pending slots.
    owners = {
        owner
        for item in list_operations()
        if item.operation_id and set(item.slot_ids) & set(request.slot_ids)
        if (operation := get_operation(item.operation_id)) is not None
        for owner in [operation[1]]
    }
    if owners:
        if len(owners) == 1:
            existing = get_booking_task(next(iter(owners)))
            if {slot_id for item in existing.items for slot_id in item.slot_ids} == set(request.slot_ids):
                return existing
        raise HTTPException(
            status_code=409, detail={"message": "Slots already have booking operations", "task_ids": sorted(owners)}
        )
    index = await _load_review_index()
    items: list[BookingTaskItem] = []
    seen: set[str] = set()
    for slot_id in dict.fromkeys(request.slot_ids):
        reviewed = index.slots.get(slot_id)
        if reviewed is None:
            raise HTTPException(status_code=404, detail="Unknown booking slot")
        if reviewed.review_kind not in {ReviewKind.READY, ReviewKind.CONFLICT}:
            raise HTTPException(
                status_code=409, detail="Slot has an existing or uncertain booking; reconcile before sending"
            )
        for payload in collect_booking_payloads(index, [slot_id], request.conflict_modes):
            key = payload_key(payload)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                BookingTaskItem(
                    index=str(len(items)),
                    title=payload.get("title"),
                    status=BookingTaskItemStatus.PENDING,
                    payload=payload,
                    slot_ids=[slot_id],
                    room_id=payload.get("room_id"),
                )
            )
    task, created = _reserve(BookingTaskKind.BOOK, items)
    if created:
        _spawn(_run_task(task.task_id))
    return task


def _record(item: BookingTaskItem, outcome: BookingOutcome, *, action: str) -> None:
    item.outcome = outcome
    item.history.append(
        {
            "at": utcnow().isoformat(),
            "action": action,
            "outcome": outcome,
            **{
                key: getattr(item, key).isoformat()
                if isinstance(getattr(item, key), dtm.datetime)
                else getattr(item, key)
                for key in BookingEvidence.model_fields
            },
        }
    )


def _apply_evidence(item: BookingTaskItem, evidence: BookingEvidence, *, cancelling: bool = False) -> None:
    # Evidence from older reads must not overwrite a later room decision.
    if evidence.checked_at and item.checked_at and evidence.checked_at < item.checked_at:
        return
    for field in evidence.model_fields_set:
        if field in BookingEvidence.model_fields and field != "operation_id":
            value = getattr(evidence, field)
            if value is not None or field == "message_body":
                setattr(item, field, value)
    item.can_cancel = bool(item.outlook_booking_id and item.organizer_mailbox)
    if cancelling:
        outcome = BookingOutcome.CANCEL_REQUESTED
        if evidence.checked_at and evidence.room_presence == "absent" and evidence.organizer_presence == "absent":
            outcome = BookingOutcome.CANCELLED
            item.can_cancel = False
    else:
        outcome = {
            "Accept": BookingOutcome.ACCEPTED,
            "Tentative": BookingOutcome.PENDING_APPROVAL,
            "Decline": BookingOutcome.DECLINED,
        }.get(item.room_response or "Unknown", BookingOutcome.UNKNOWN)
    _record(item, outcome, action="evidence")


def _complete(task: BookingTask) -> None:
    task.done = sum(item.status in {BookingTaskItemStatus.OK, BookingTaskItemStatus.ERROR} for item in task.items)
    task.status = BookingTaskStatus.DONE
    if task.kind == BookingTaskKind.BOOK:
        task.book = book_result_from_items(task.items)
    else:
        task.cancel = cancel_result_from_items(task.items)
    save_task(task)


async def _reconcile(task: BookingTask) -> None:
    if not task.items:
        _complete(task)
        return
    entries = [
        {
            "operation_id": item.payload.get("operation_id"),
            "outlook_booking_id": item.outlook_booking_id,
            "uid": item.uid,
            "room_id": item.room_id,
            "organizer_mailbox": item.organizer_mailbox,
            "scope": item.cancellation_scope or "series",
            "start": item.payload.get("start"),
            "end": item.payload.get("end"),
        }
        for item in task.items
    ]
    try:
        evidence_list = await booking_client.reconcile_auto_bookings(entries)
        by_operation = {evidence.operation_id: evidence for evidence in evidence_list if evidence.operation_id}
        for item in task.items:
            if task.kind == BookingTaskKind.BOOK and item.outcome in {
                BookingOutcome.CANCEL_REQUESTED,
                BookingOutcome.CANCELLED,
            }:
                continue
            evidence = by_operation.get(item.payload.get("operation_id") or "")
            if evidence is None and not item.payload.get("operation_id"):
                matches = [
                    candidate
                    for candidate in evidence_list
                    if candidate.room_id == item.room_id
                    and (
                        (item.uid is not None and candidate.uid == item.uid)
                        or (
                            item.outlook_booking_id is not None
                            and candidate.outlook_booking_id == item.outlook_booking_id
                        )
                    )
                ]
                evidence = matches[0] if len(matches) == 1 else None
            if evidence is None:
                item.error = item.error or "No correlated reconciliation evidence"
                if item.outcome in {BookingOutcome.UNKNOWN, BookingOutcome.SUBMITTED}:
                    _record(item, BookingOutcome.UNKNOWN, action="reconcile_missing")
            else:
                _apply_evidence(item, evidence, cancelling=task.kind == BookingTaskKind.CANCEL)
                item.error = None
            if item.status in {BookingTaskItemStatus.PENDING, BookingTaskItemStatus.SENT}:
                item.status = (
                    BookingTaskItemStatus.ERROR if item.outcome == BookingOutcome.UNKNOWN else BookingTaskItemStatus.OK
                )
    except (httpx.HTTPError, ValueError) as error:
        for item in task.items:
            item.error = str(error)
            if item.status in {BookingTaskItemStatus.PENDING, BookingTaskItemStatus.SENT}:
                item.status = BookingTaskItemStatus.ERROR
            # A failed read cannot prove absence or revoke a known room response.
            if item.outcome == BookingOutcome.SUBMITTED:
                _record(item, BookingOutcome.UNKNOWN, action="reconcile_failed")
    _complete(task)


async def reconcile_booking_task(task_id: str) -> BookingTask:
    with task_lock(task_id) as acquired:
        task = get_booking_task(task_id)
        if acquired:
            await _reconcile(task)
    return get_booking_task(task_id)


async def recover_pending_tasks() -> None:
    # Bounded startup pass; older tasks remain available for explicit reconciliation.
    for task in list_tasks(limit=100):
        if task.status in {BookingTaskStatus.QUEUED, BookingTaskStatus.RUNNING} or any(
            item.outcome
            in {
                BookingOutcome.UNKNOWN,
                BookingOutcome.SUBMITTED,
                BookingOutcome.PENDING_APPROVAL,
                BookingOutcome.CANCEL_REQUESTED,
            }
            for item in task.items
        ):
            try:
                await reconcile_booking_task(task.task_id)
            except Exception:  # noqa: BLE001 — isolate recovery failures between durable tasks
                logger.exception("Booking recovery failed for task %s", task.task_id)


def start_recovery() -> None:
    _spawn(recover_pending_tasks())


async def _run_task(task_id: str) -> None:
    with task_lock(task_id) as acquired:
        if not acquired:
            return
        task = get_booking_task(task_id)
        if task.status != BookingTaskStatus.QUEUED:
            return
        task.status = BookingTaskStatus.RUNNING
        # Commit uncertainty before the network boundary, even if process dies before SENT.
        for item in task.items:
            _record(
                item,
                BookingOutcome.SUBMITTED if task.kind == BookingTaskKind.BOOK else BookingOutcome.CANCEL_REQUESTED,
                action="dispatch_started",
            )
        save_task(task)
        try:
            async with asyncio.timeout(TASK_TIMEOUT_SECONDS):
                if task.kind == BookingTaskKind.BOOK:
                    await _book_task_body(task)
                else:
                    await _cancel_task_body(task)
        except Exception as error:  # noqa: BLE001 — preserve unknown outcomes for every transport failure
            logger.warning("Booking task transport failed: %s", error)
            task.error = str(error)
            for item in task.items:
                if item.status in {BookingTaskItemStatus.PENDING, BookingTaskItemStatus.SENT}:
                    item.status = BookingTaskItemStatus.ERROR
                    item.error = str(error)
                    if task.kind == BookingTaskKind.BOOK:
                        _record(item, BookingOutcome.UNKNOWN, action="transport_failed")
            save_task(task)
            await _reconcile(task)
        else:
            _complete(task)


async def _book_task_body(task: BookingTask) -> None:
    if not task.items:
        return
    by_index = {item.index: item for item in task.items}
    async for event in booking_client.stream_auto_bookings_batch([item.payload for item in task.items]):
        if event.event == BmpStreamEventKind.PING:
            continue
        if event.event == BmpStreamEventKind.SENT:
            for event_index in event.indexes or ([event.index] if event.index is not None else []):
                item = by_index.get(event_index)
                if item is not None:
                    item.status = BookingTaskItemStatus.SENT
            evidence_entries = event.items or ([event.booking] if event.booking else [event])
            for evidence in evidence_entries:
                item = next((item for item in task.items if evidence.operation_id == item.operation_id), None)
                if item is not None:
                    _apply_evidence(item, evidence)
            task.sent = sum(item.status != BookingTaskItemStatus.PENDING for item in task.items)
        elif event.event == BmpStreamEventKind.ITEM and event.index is not None:
            item = by_index.get(event.index)
            if item is not None:
                evidence = event.booking or event
                if evidence.operation_id and evidence.operation_id != item.operation_id:
                    raise ValueError("BMP returned mismatched operation identity")
                _apply_evidence(item, evidence)
                item.status = BookingTaskItemStatus(event.status or "error")
                item.error = event.error
                task.current = item.title
        elif event.event == BmpStreamEventKind.DONE:
            break
        save_task(task)
    if any(item.status in {BookingTaskItemStatus.PENDING, BookingTaskItemStatus.SENT} for item in task.items):
        await _reconcile(task)


def _cancel_item(
    source: BookingTaskItem, *, index: str, scope: Literal["series", "occurrence"], occurrence_date: dtm.date | None
) -> BookingTaskItem:
    if not source.outlook_booking_id or not source.organizer_mailbox:
        raise HTTPException(status_code=409, detail="Cancellation requires a verified manageable organizer identity")
    if scope == "occurrence" and occurrence_date is None:
        raise HTTPException(status_code=422, detail="occurrence_date is required for occurrence cancellation")
    payload = {
        "operation_id": source.operation_id,
        "uid": source.uid,
        "organizer_mailbox": source.organizer_mailbox,
        "outlook_booking_id": source.outlook_booking_id,
        "room_id": source.room_id,
        "start": source.payload.get("start"),
        "end": source.payload.get("end"),
        "title": source.title,
        "scope": scope,
        "occurrence_date": occurrence_date.isoformat() if occurrence_date else None,
    }
    if scope == "occurrence":
        occurrences = (
            iter_payload_occurrences(source.payload)
            if isinstance(source.payload.get("recurrence"), dict)
            else iter_booking_occurrences(source.payload)
        )
        matching = [(start, end) for start, end in occurrences if start.date() == occurrence_date]
        if len(matching) != 1:
            raise HTTPException(status_code=409, detail="Occurrence is not uniquely identified by the saved booking")
        start, end = matching[0]
        payload["start"], payload["end"] = start.isoformat(), end.isoformat()
    return BookingTaskItem(
        **{key: getattr(source, key) for key in BookingEvidence.model_fields},
        index=index,
        title=source.title,
        status=BookingTaskItemStatus.PENDING,
        outcome=BookingOutcome.CANCEL_REQUESTED,
        payload=payload,
        cancellation_scope=scope,
        occurrence_date=occurrence_date,
        source_operation_id=source.operation_id,
    )


async def start_cancel_booking(request: CancelBookingRequest) -> BookingTask:
    items = []
    for operation_id in dict.fromkeys(request.operation_ids):
        operation = get_operation(operation_id)
        if operation is None or operation[0].cancellation_scope is not None:
            raise HTTPException(status_code=404, detail="Booking operation not found")
        items.append(
            _cancel_item(operation[0], index=operation_id, scope=request.scope, occurrence_date=request.occurrence_date)
        )
    if request.booking_ids:
        window = _booking_window(_require_term())
        if window is None:
            raise HTTPException(status_code=409, detail="No checked booking window")
        try:
            bookings = await booking_client.get_auto_bookings(*window)
        except httpx.HTTPError as error:
            raise HTTPException(status_code=502, detail="Unable to verify organizer bookings") from error
        known = {booking.outlook_booking_id: booking for booking in bookings if booking.outlook_booking_id}
        for booking_id in dict.fromkeys(request.booking_ids):
            if any(item.outlook_booking_id == booking_id for item in items):
                continue
            persisted = next(
                (
                    item
                    for item in list_operations()
                    if item.outlook_booking_id == booking_id and item.cancellation_scope is None
                ),
                None,
            )
            if persisted is not None:
                source = persisted
            else:
                booking = known.get(booking_id)
                if booking is None:
                    raise HTTPException(status_code=404, detail="Manageable Auto booking not found")
                payload = booking.model_dump(mode="json")
                payload["start"], payload["end"] = payload.pop("start_time"), payload.pop("end_time")
                source = BookingTaskItem(
                    **BookingEvidence.model_validate(payload).model_dump(),
                    index=booking_id,
                    title=booking.title,
                    status=BookingTaskItemStatus.OK,
                    payload=payload,
                )
            items.append(
                _cancel_item(source, index=booking_id, scope=request.scope, occurrence_date=request.occurrence_date)
            )
    task, created = _reserve(BookingTaskKind.CANCEL, items)
    if created:
        _spawn(_run_task(task.task_id))
    return task


async def start_cancel_extra(request: CancelExtraRequest) -> BookingTask:
    index = await _load_review_index()
    items = []
    for extra_id in dict.fromkeys(request.extra_ids):
        booking = index.extras.get(extra_id)
        if booking is None:
            raise HTTPException(status_code=404, detail="Unknown extra booking")
        if not booking.get("can_cancel"):
            raise HTTPException(
                status_code=409,
                detail="Extra booking requires manual review; cancellation may remove required teaching dates",
            )
        evidence = BookingEvidence.model_validate(booking)
        source = BookingTaskItem(
            **evidence.model_dump(),
            index=extra_id,
            title=booking.get("title"),
            status=BookingTaskItemStatus.OK,
            payload=booking,
        )
        items.append(_cancel_item(source, index=extra_id, scope=request.scope, occurrence_date=request.occurrence_date))
    task, created = _reserve(BookingTaskKind.CANCEL, items)
    if created:
        _spawn(_run_task(task.task_id))
    return task


async def _cancel_task_body(task: BookingTask) -> None:
    for item in task.items:
        try:
            evidence = await booking_client.cancel_booking_intent(item.payload)
            _apply_evidence(item, evidence, cancelling=True)
            item.status = BookingTaskItemStatus.OK
        except (httpx.HTTPError, ValueError) as error:
            item.status = BookingTaskItemStatus.ERROR
            item.error = str(error)
        save_task(task)
    await _reconcile(task)
