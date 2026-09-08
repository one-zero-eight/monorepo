import hashlib
import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.schedule_assistant.db.models import BookingOperationRow, BookingTaskRow
from src.schedule_assistant.db.session import get_engine
from src.schedule_assistant.modules.bookings.match import iter_payload_occurrences
from src.schedule_assistant.modules.bookings.schemas import (
    BatchBookItemResult,
    BatchBookResponse,
    BookingEvidence,
    BookingItemResultStatus,
    BookingOutcome,
    BookingTask,
    BookingTaskItem,
    BookingTaskItemStatus,
    BookingTaskKind,
    BookingTaskStatus,
    CancelExtraResponse,
)
from src.schedule_assistant.utcnow import utcnow


class ReservationConflictError(Exception):
    def __init__(self, task_ids: list[str]) -> None:
        self.task_ids = task_ids
        super().__init__("Booking operation already reserved")


def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def payload_key(payload: dict[str, Any]) -> str:
    canonical = {key: value for key, value in payload.items() if key != "operation_id"}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@contextmanager
def task_lock(task_id: str) -> Iterator[bool]:
    """A process death releases the lock; recovery only reads Exchange, never dispatches."""
    lock_id = int.from_bytes(hashlib.sha256(task_id.encode()).digest()[:8], signed=True)
    with _session_factory()() as session, session.begin():
        yield bool(session.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_id}))


def _row_to_task(row: BookingTaskRow, session: Session) -> BookingTask:
    items = [BookingTaskItem.model_validate(item) for item in (row.items or [])]
    for index, item in enumerate(items):
        operation = session.get(BookingOperationRow, item.operation_id) if item.operation_id else None
        if operation is not None:
            items[index] = BookingTaskItem.model_validate(operation.item)
    task = BookingTask(
        task_id=row.id,
        kind=BookingTaskKind(row.kind),
        status=BookingTaskStatus(row.status),
        sent=row.sent,
        done=row.done,
        total=row.total,
        current=row.current,
        items=items,
        error=row.error,
    )
    if row.result is not None:
        if task.kind == BookingTaskKind.BOOK:
            task.book = book_result_from_items(items)
        else:
            task.cancel = cancel_result_from_items(items)
    return task


def create_task(*, kind: BookingTaskKind, items: list[BookingTaskItem], current: str | None = None) -> BookingTask:
    """Reserve the entire batch and persist exact payloads in one transaction before sending."""
    now = utcnow()
    task_id = str(uuid.uuid4())
    keys = [payload_key(item.payload) for item in items]
    row = BookingTaskRow(
        id=task_id,
        kind=kind,
        status=BookingTaskStatus.QUEUED,
        sent=0,
        done=0,
        total=len(items),
        current=current,
        items=[],
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
    )
    for item in items:
        item.operation_id = str(uuid.uuid4())
        item.payload = {
            **item.payload,
            "operation_id": item.operation_id if kind == BookingTaskKind.BOOK else item.source_operation_id,
        }
        item.history = [{"at": now.isoformat(), "outcome": item.outcome, "action": "reserved"}]
    row.items = [item.model_dump(mode="json") for item in items]
    try:
        with _session_factory()() as session:
            if kind == BookingTaskKind.BOOK:
                rooms = sorted({item.room_id for item in items if item.room_id})
                for room in rooms:
                    lock_id = int.from_bytes(hashlib.sha256(f"booking-room:{room}".encode()).digest()[:8], signed=True)
                    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
                reservations = session.scalars(
                    select(BookingOperationRow).where(BookingOperationRow.reservation_key.like("book:%"))
                )
                owners = set()
                for reservation in reservations:
                    reserved = BookingTaskItem.model_validate(reservation.item)
                    if reserved.room_id not in rooms:
                        continue
                    for item in items:
                        if item.room_id != reserved.room_id:
                            continue
                        if any(
                            start < reserved_end and reserved_start < end
                            for start, end in iter_payload_occurrences(item.payload)
                            for reserved_start, reserved_end in iter_payload_occurrences(reserved.payload)
                        ):
                            owners.add(reservation.task_id)
                if owners:
                    raise ReservationConflictError(sorted(owners))
            session.add(row)
            for item, key in zip(items, keys, strict=True):
                session.add(
                    BookingOperationRow(
                        id=item.operation_id,
                        reservation_key=f"{kind}:{key}",
                        task_id=task_id,
                        item=item.model_dump(mode="json"),
                        created_at=now,
                        updated_at=now,
                    )
                )
            session.commit()
            return _row_to_task(row, session)
    except IntegrityError as error:
        with _session_factory()() as session:
            owners = list(
                session.scalars(
                    select(BookingOperationRow.task_id).where(
                        BookingOperationRow.reservation_key.in_([f"{kind}:{key}" for key in keys])
                    )
                ).unique()
            )
        if not owners:
            raise
        raise ReservationConflictError(owners) from error


def get_task(task_id: str) -> BookingTask | None:
    with _session_factory()() as session:
        row = session.get(BookingTaskRow, task_id)
        return _row_to_task(row, session) if row is not None else None


def list_tasks(*, limit: int = 100, offset: int = 0) -> list[BookingTask]:
    with _session_factory()() as session:
        rows = session.scalars(
            select(BookingTaskRow)
            .order_by(BookingTaskRow.created_at.desc(), BookingTaskRow.id)
            .offset(offset)
            .limit(limit)
        )
        return [_row_to_task(row, session) for row in rows]


def list_operations() -> list[BookingTaskItem]:
    with _session_factory()() as session:
        rows = session.scalars(select(BookingOperationRow).where(BookingOperationRow.reservation_key.is_not(None)))
        return [BookingTaskItem.model_validate(row.item) for row in rows]


def get_operation(operation_id: str) -> tuple[BookingTaskItem, str] | None:
    with _session_factory()() as session:
        row = session.get(BookingOperationRow, operation_id)
        return (BookingTaskItem.model_validate(row.item), row.task_id) if row is not None else None


def save_task(task: BookingTask) -> BookingTask:
    with _session_factory()() as session:
        row = session.get(BookingTaskRow, task.task_id)
        if row is None:
            raise KeyError(task.task_id)
        row.status = task.status
        row.sent = task.sent
        row.done = task.done
        row.total = task.total
        row.current = task.current
        row.items = [item.model_dump(mode="json") for item in task.items]
        row.error = task.error
        row.result = (
            task.book.model_dump(mode="json")
            if task.book
            else (task.cancel.model_dump(mode="json") if task.cancel else None)
        )
        row.updated_at = utcnow()
        for item in task.items:
            operation = (
                session.get(BookingOperationRow, item.operation_id, with_for_update=True) if item.operation_id else None
            )
            if operation is None:
                continue
            persisted = BookingTaskItem.model_validate(operation.item)
            if task.kind == BookingTaskKind.BOOK and persisted.outcome in {
                BookingOutcome.CANCEL_REQUESTED,
                BookingOutcome.CANCELLED,
            }:
                continue
            operation.item = item.model_dump(mode="json")
            operation.updated_at = utcnow()
            if item.outcome == BookingOutcome.CANCELLED:
                operation.reservation_key = None
            if item.source_operation_id and item.cancellation_scope == "series":
                source = session.get(BookingOperationRow, item.source_operation_id, with_for_update=True)
                if source is not None:
                    original = BookingTaskItem.model_validate(source.item)
                    original.outcome = item.outcome
                    known_entries = {json.dumps(entry, sort_keys=True) for entry in original.history}
                    original.history = [
                        *original.history,
                        *[entry for entry in item.history if json.dumps(entry, sort_keys=True) not in known_entries],
                    ]
                    for field in BookingEvidence.model_fields:
                        if field != "operation_id":
                            setattr(original, field, getattr(item, field))
                    source.item = original.model_dump(mode="json")
                    source.updated_at = utcnow()
                    if item.outcome == BookingOutcome.CANCELLED:
                        source.reservation_key = None
        session.commit()
        return _row_to_task(row, session)


def book_result_from_items(items: list[BookingTaskItem]) -> BatchBookResponse:
    return BatchBookResponse(
        submitted=len(items),
        results=[
            BatchBookItemResult(
                **{key: getattr(item, key) for key in BookingEvidence.model_fields},
                index=item.index,
                title=item.title,
                outcome=item.outcome,
                status=BookingItemResultStatus.OK
                if item.status == BookingTaskItemStatus.OK
                else BookingItemResultStatus.ERROR,
                error=item.error,
            )
            for item in items
        ],
    )


def cancel_result_from_items(items: list[BookingTaskItem]) -> CancelExtraResponse:
    return CancelExtraResponse(
        cancelled=[item.index for item in items if item.outcome == BookingOutcome.CANCELLED],
        cancel_requested=[item.index for item in items if item.outcome == BookingOutcome.CANCEL_REQUESTED],
        failed={
            item.index: item.error or "Cancellation is not yet verified"
            for item in items
            if item.outcome != BookingOutcome.CANCELLED
        },
    )
