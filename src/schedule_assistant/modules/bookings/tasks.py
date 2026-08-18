import uuid
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from src.schedule_assistant.db.models import BookingTaskRow
from src.schedule_assistant.db.session import get_engine
from src.schedule_assistant.modules.bookings.schemas import (
    BatchBookItemResult,
    BatchBookResponse,
    BookingItemResultStatus,
    BookingTask,
    BookingTaskItem,
    BookingTaskItemStatus,
    BookingTaskKind,
    BookingTaskStatus,
    CancelExtraResponse,
)
from src.schedule_assistant.utcnow import utcnow


def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def _row_to_task(row: BookingTaskRow) -> BookingTask:
    items = [BookingTaskItem.model_validate(item) for item in (row.items or [])]
    book = None
    cancel = None
    if row.kind == BookingTaskKind.BOOK and row.result:
        book = BatchBookResponse.model_validate(row.result)
    if row.kind == BookingTaskKind.CANCEL and row.result:
        cancel = CancelExtraResponse.model_validate(row.result)
    return BookingTask.model_validate(
        {
            "task_id": row.id,
            "kind": row.kind,
            "status": row.status,
            "sent": row.sent,
            "done": row.done,
            "total": row.total,
            "current": row.current,
            "items": items,
            "error": row.error,
            "book": book,
            "cancel": cancel,
        }
    )


def create_task(*, kind: BookingTaskKind, items: list[BookingTaskItem], current: str | None = None) -> BookingTask:
    now = utcnow()
    row = BookingTaskRow(
        id=str(uuid.uuid4()),
        kind=kind,
        status=BookingTaskStatus.QUEUED,
        sent=0,
        done=0,
        total=len(items),
        current=current,
        items=[item.model_dump() for item in items],
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
    )
    with _session_factory()() as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_task(row)


def get_task(task_id: str) -> BookingTask | None:
    with _session_factory()() as session:
        row = session.get(BookingTaskRow, task_id)
        if row is None:
            return None
        return _row_to_task(row)


def save_task(task: BookingTask) -> BookingTask:
    with _session_factory()() as session:
        row = session.get(BookingTaskRow, task.task_id)
        if row is None:
            raise KeyError(task.task_id)
        row.kind = task.kind
        row.status = task.status
        row.sent = task.sent
        row.done = task.done
        row.total = task.total
        row.current = task.current
        row.items = [item.model_dump() for item in task.items]
        row.error = task.error
        result: dict[str, Any] | None = None
        if task.kind == BookingTaskKind.BOOK and task.book is not None:
            result = task.book.model_dump()
        if task.kind == BookingTaskKind.CANCEL and task.cancel is not None:
            result = task.cancel.model_dump()
        row.result = result
        row.updated_at = utcnow()
        session.commit()
        session.refresh(row)
        return _row_to_task(row)


def book_result_from_items(items: list[BookingTaskItem]) -> BatchBookResponse:
    results: list[BatchBookItemResult] = []
    for item in items:
        status = (
            BookingItemResultStatus.OK if item.status == BookingTaskItemStatus.OK else BookingItemResultStatus.ERROR
        )
        error = item.error
        if item.status not in {BookingTaskItemStatus.OK, BookingTaskItemStatus.ERROR}:
            error = error or "unfinished"
            error = error or "unfinished"
        results.append(
            BatchBookItemResult(
                index=item.index,
                status=status,
                title=item.title,
                error=error,
            )
        )
    return BatchBookResponse(submitted=len(items), results=results)


def cancel_result_from_items(items: list[BookingTaskItem]) -> CancelExtraResponse:
    cancelled: list[str] = []
    failed: dict[str, str] = {}
    for item in items:
        if item.status == BookingTaskItemStatus.OK:
            cancelled.append(item.index)
        else:
            failed[item.index] = item.error or "unfinished"
    return CancelExtraResponse(cancelled=cancelled, failed=failed)
