import asyncio
import datetime as dtm
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from src.schedule_assistant.modules.bookings.client import BmpStreamEvent, BookingClient
from src.schedule_assistant.modules.bookings.schemas import (
    BookingEvidence,
    BookingOutcome,
    BookingTaskItem,
    BookingTaskItemStatus,
    BookingTaskKind,
)
from src.schedule_assistant.modules.bookings.service import recover_pending_tasks
from src.schedule_assistant.modules.bookings.tasks import ReservationConflictError, create_task, get_task
from tests.schedule_assistant.test_booking_flow import _occurrence_courses, _seed, _wait_task


@pytest.fixture(autouse=True)
def booking_clock(monkeypatch):
    from tests.schedule_assistant.test_booking_flow import _freeze_booking_now

    _freeze_booking_now(monkeypatch, dtm.datetime(2026, 6, 1, tzinfo=dtm.UTC))
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])


def _item() -> BookingTaskItem:
    return BookingTaskItem(
        index="0",
        title="Algorithms (lec)",
        status=BookingTaskItemStatus.PENDING,
        room_id="107",
        slot_ids=["slot"],
        payload={
            "title": "Algorithms (lec)",
            "room_id": "107",
            "start": "2026-06-08T14:20:00+03:00",
            "end": "2026-06-08T15:50:00+03:00",
        },
    )


def test_atomic_reservation_across_database_connections(bookings_repo):
    def reserve():
        try:
            return create_task(kind=BookingTaskKind.BOOK, items=[_item()]).task_id
        except ReservationConflictError as error:
            return error.task_ids[0]

    with ThreadPoolExecutor(max_workers=4) as executor:
        ids = list(executor.map(lambda _: reserve(), range(4)))
    assert len(set(ids)) == 1
    task = get_task(ids[0])
    assert task is not None
    persisted = task.items[0]
    assert persisted.payload["operation_id"] == persisted.operation_id
    assert persisted.history[0]["action"] == "reserved"


@pytest.mark.asyncio
async def test_existing_booking_cancel_uses_exchange_identity_not_new_task_marker(bookings_repo, mock_booking_client):
    from src.schedule_assistant.modules.bookings.service import reconcile_booking_task

    item = _item()
    item.outlook_booking_id = "existing-ews-id"
    item.uid = "existing-uid"
    item.organizer_mailbox = "bmp@test.invalid"
    item.cancellation_scope = "series"
    item.outcome = BookingOutcome.CANCEL_REQUESTED
    task = create_task(kind=BookingTaskKind.CANCEL, items=[item])
    assert task.items[0].payload["operation_id"] is None
    mock_booking_client.reconcile_auto_bookings.return_value = [
        BookingEvidence(
            room_id="107",
            outlook_booking_id="existing-ews-id",
            uid="existing-uid",
            organizer_presence="absent",
            room_presence="absent",
            checked_at=dtm.datetime(2026, 6, 1, tzinfo=dtm.UTC),
        )
    ]
    restored = await reconcile_booking_task(task.task_id)
    assert restored.items[0].outcome == BookingOutcome.CANCELLED
    assert mock_booking_client.reconcile_auto_bookings.call_args.args[0][0]["operation_id"] is None
    mock_booking_client.stream_auto_bookings_batch.assert_not_called()


@pytest.mark.asyncio
async def test_restart_reconciles_without_resending(authenticated_client, bookings_repo, mock_booking_client):
    task = create_task(kind=BookingTaskKind.BOOK, items=[_item()])
    operation_id = task.items[0].operation_id
    mock_booking_client.reconcile_auto_bookings.return_value = [
        BookingEvidence(
            operation_id=operation_id,
            room_id="107",
            outlook_booking_id="ews-id",
            uid="uid-1",
            organizer_mailbox="bmp@test.invalid",
            room_response="Tentative",
            room_presence="present",
            checked_at=dtm.datetime(2026, 6, 1, tzinfo=dtm.UTC),
            message_body="Awaiting approval",
        )
    ]
    await recover_pending_tasks()
    response = await authenticated_client.get("/bookings/tasks")
    restored = response.json()[0]
    assert restored["task_id"] == task.task_id
    assert restored["items"][0]["outcome"] == "pending_approval"
    assert restored["items"][0]["uid"] == "uid-1"
    assert restored["items"][0]["can_cancel"] is True
    mock_booking_client.stream_auto_bookings_batch.assert_not_called()


@pytest.mark.asyncio
async def test_sent_identity_survives_drop_and_blocks_duplicate(
    authenticated_client, bookings_repo, mock_booking_client
):
    _seed(bookings_repo, courses=_occurrence_courses())
    mock_booking_client.get_all_bookings.return_value = []
    mock_booking_client.get_auto_bookings.return_value = []
    mock_booking_client.reconcile_auto_bookings.side_effect = httpx.ReadError("room calendar unavailable")
    sends = []

    async def stream(payloads):
        sends.extend(payloads)
        operation_id = payloads[0]["operation_id"]
        yield BmpStreamEvent.model_validate(
            {
                "event": "sent",
                "indexes": ["0"],
                "items": [
                    {
                        "operation_id": operation_id,
                        "outlook_booking_id": "saved-before-response",
                        "uid": "uid-2",
                        "organizer_mailbox": "bmp@test.invalid",
                        "room_id": "107",
                    }
                ],
            }
        )
        raise httpx.ReadError("stream interrupted")

    mock_booking_client.stream_auto_bookings_batch = stream
    review = (await authenticated_client.get("/bookings/review")).json()
    slot_id = review["programs"][0]["courses"][0]["components"][0]["slots"][0]["slot_id"]
    request = {"slot_ids": [slot_id]}
    first, second = await asyncio.gather(
        authenticated_client.post("/bookings/batch", json=request),
        authenticated_client.post("/bookings/batch", json=request),
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["task_id"] == second.json()["task_id"]
    task = await _wait_task(authenticated_client, first.json()["task_id"])
    assert task["items"][0]["outlook_booking_id"] == "saved-before-response"
    assert task["items"][0]["outcome"] == "unknown"
    third = await authenticated_client.post("/bookings/batch", json=request)
    assert third.json()["task_id"] == task["task_id"]
    assert len(sends) == 1
    restored_review = (await authenticated_client.get("/bookings/review")).json()
    assert restored_review["programs"][0]["courses"][0]["components"][0]["slots"][0]["review_kind"] == "unknown"


@pytest.mark.asyncio
async def test_auto_booking_read_error_is_not_empty(authenticated_client, bookings_repo, mock_booking_client):
    _seed(bookings_repo, courses=_occurrence_courses())
    mock_booking_client.get_all_bookings.return_value = []
    mock_booking_client.get_auto_bookings.side_effect = httpx.ReadError("incomplete calendar")
    response = await authenticated_client.get("/bookings/review")
    assert response.status_code == 502
    assert "incomplete calendar" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cancel_pending_requires_both_calendars_absent(authenticated_client, bookings_repo, mock_booking_client):
    source = create_task(kind=BookingTaskKind.BOOK, items=[_item()])
    operation_id = source.items[0].operation_id
    evidence = BookingEvidence(
        operation_id=operation_id,
        room_id="107",
        outlook_booking_id="ews-3",
        uid="uid-3",
        organizer_mailbox="bmp@test.invalid",
        room_response="Tentative",
        room_presence="present",
        organizer_presence="present",
        checked_at=dtm.datetime(2026, 6, 1, tzinfo=dtm.UTC),
    )
    mock_booking_client.reconcile_auto_bookings.return_value = [evidence]
    await authenticated_client.post(f"/bookings/tasks/{source.task_id}/reconcile")
    mock_booking_client.cancel_booking_intent.return_value = evidence
    response = await authenticated_client.post(
        "/bookings/cancel", json={"operation_ids": [operation_id], "scope": "series"}
    )
    assert response.status_code == 200
    task = await _wait_task(authenticated_client, response.json()["task_id"])
    assert task["items"][0]["outcome"] == "cancel_requested"
    assert task["cancel"]["cancelled"] == []
    source_task = get_task(source.task_id)
    assert source_task is not None
    assert source_task.items[0].outcome == BookingOutcome.CANCEL_REQUESTED
    missing = await authenticated_client.post("/bookings/cancel", json={"operation_ids": [operation_id]})
    assert missing.status_code == 422
    evidence = evidence.model_copy(
        update={
            "room_presence": "absent",
            "organizer_presence": "absent",
            "checked_at": dtm.datetime(2026, 6, 2, tzinfo=dtm.UTC),
        }
    )
    mock_booking_client.reconcile_auto_bookings.return_value = [evidence]
    reconciled = await authenticated_client.post(f"/bookings/tasks/{task['task_id']}/reconcile")
    assert reconciled.json()["items"][0]["outcome"] == "cancelled"
    original_task = get_task(source.task_id)
    assert original_task is not None
    original = original_task.items[0]
    assert original.outcome == BookingOutcome.CANCELLED
    assert any(entry["outcome"] == "cancel_requested" for entry in original.history)
    # Reservation is released only after verified cancellation.
    assert create_task(kind=BookingTaskKind.BOOK, items=[_item()]).task_id != source.task_id


def test_overlapping_changed_payload_is_reserved_atomically(bookings_repo):
    first = create_task(kind=BookingTaskKind.BOOK, items=[_item()])
    changed = _item()
    changed.payload["title"] = "Another course"
    changed.payload["start"] = "2026-06-08T14:30:00+03:00"
    with pytest.raises(ReservationConflictError) as error:
        create_task(kind=BookingTaskKind.BOOK, items=[changed])
    assert error.value.task_ids == [first.task_id]
    adjacent = _item()
    adjacent.payload["start"] = "2026-06-08T16:00:00+03:00"
    adjacent.payload["end"] = "2026-06-08T17:30:00+03:00"
    assert create_task(kind=BookingTaskKind.BOOK, items=[adjacent]).task_id != first.task_id


@pytest.mark.asyncio
async def test_late_decline_persists_and_stale_tentative_does_not_replace_it(
    authenticated_client, bookings_repo, mock_booking_client
):
    task = create_task(kind=BookingTaskKind.BOOK, items=[_item()])
    pending = BookingEvidence(
        operation_id=task.items[0].operation_id,
        room_id="107",
        uid="late-uid",
        outlook_booking_id="late-id",
        organizer_mailbox="bmp@test.invalid",
        room_response="Tentative",
        room_presence="present",
        checked_at=dtm.datetime(2026, 6, 1, tzinfo=dtm.UTC),
    )
    mock_booking_client.reconcile_auto_bookings.return_value = [pending]
    await authenticated_client.post(f"/bookings/tasks/{task.task_id}/reconcile")
    decline = pending.model_copy(
        update={
            "room_response": "Decline",
            "message_body": "Conflicting dates",
            "checked_at": dtm.datetime(2026, 6, 2, tzinfo=dtm.UTC),
        }
    )
    mock_booking_client.reconcile_auto_bookings.return_value = [decline]
    response = await authenticated_client.post(f"/bookings/tasks/{task.task_id}/reconcile")
    assert response.json()["items"][0]["outcome"] == "declined"
    mock_booking_client.reconcile_auto_bookings.return_value = [pending]
    response = await authenticated_client.post(f"/bookings/tasks/{task.task_id}/reconcile")
    assert response.json()["items"][0]["outcome"] == "declined"
    assert response.json()["items"][0]["message_body"] == "Conflicting dates"


@pytest.mark.asyncio
async def test_occurrence_cancel_uses_saved_exact_window(authenticated_client, bookings_repo, mock_booking_client):
    item = _item()
    item.payload["recurrence"] = {"weekday": "monday", "start_date": "2026-06-08", "until_date": "2026-06-29"}
    task = create_task(kind=BookingTaskKind.BOOK, items=[item])
    operation_id = task.items[0].operation_id
    evidence = BookingEvidence(
        operation_id=operation_id,
        room_id="107",
        outlook_booking_id="master",
        uid="series",
        organizer_mailbox="bmp@test.invalid",
        room_response="Tentative",
        room_presence="present",
        checked_at=dtm.datetime(2026, 6, 1, tzinfo=dtm.UTC),
    )
    mock_booking_client.reconcile_auto_bookings.return_value = [evidence]
    mock_booking_client.cancel_booking_intent.return_value = evidence
    await authenticated_client.post(f"/bookings/tasks/{task.task_id}/reconcile")
    response = await authenticated_client.post(
        "/bookings/cancel",
        json={"operation_ids": [operation_id], "scope": "occurrence", "occurrence_date": "2026-06-15"},
    )
    assert response.status_code == 200
    await _wait_task(authenticated_client, response.json()["task_id"])
    sent = mock_booking_client.cancel_booking_intent.await_args.args[0]
    assert sent["start"] == "2026-06-15T14:20:00+03:00"
    assert sent["end"] == "2026-06-15T15:50:00+03:00"
    assert sent["scope"] == "occurrence"
    persisted_task = get_task(task.task_id)
    assert persisted_task is not None
    assert persisted_task.items[0].outcome == BookingOutcome.PENDING_APPROVAL
    invalid = await authenticated_client.post(
        "/bookings/cancel",
        json={"operation_ids": [operation_id], "scope": "occurrence", "occurrence_date": "2026-06-16"},
    )
    assert invalid.status_code == 409


@pytest.mark.asyncio
async def test_client_reconciliation_contract(respx_mock):
    client = BookingClient("https://booking.test/", "test-key")
    route = respx_mock.post("https://booking.test/bmp/auto-bookings/reconcile").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "operation_id": "op",
                    "room_id": "107",
                    "room_response": None,
                    "room_presence": "unknown",
                    "organizer_presence": "unknown",
                    "checked_at": "2026-06-01T00:00:00Z",
                    "evidence": ["read failed"],
                }
            ],
        )
    )
    evidence = await client.reconcile_auto_bookings([{"operation_id": "op", "room_id": "107"}])
    assert route.called
    assert evidence[0].room_presence == "unknown"
    assert evidence[0].evidence == ["read failed"]
