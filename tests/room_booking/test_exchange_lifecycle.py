"""Exchange boundary contracts. All EWS reads/writes are local fakes."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import exchangelib
import exchangelib.errors
import pytest
from exchangelib.items.calendar_item import MeetingResponse
from exchangelib.properties import AssociatedCalendarItemId, ConversationId
from fastapi import HTTPException

from src.room_booking.modules.bmp.repository import BmpBatchCreateEntry, BmpCalendarRepository
from src.room_booking.modules.bookings import exchange_repository as exchange_module
from src.room_booking.modules.bookings.schemas import ReconcileBookingEntry, ScopedCancelBookingRequest
from src.room_booking.modules.rooms.repository import room_repository
from tests.room_booking.datetime_helpers import msk


@pytest.fixture
def exchange_boundary(monkeypatch):
    repo = BmpCalendarRepository("https://ews.invalid/EWS/Exchange.asmx", "bmp-test@innopolis.ru", "test-only")
    calendar = MagicMock(spec=exchangelib.folders.Calendar)
    calendar.id = "calendar-id"
    calendar.account = repo.account
    repo.account.__dict__["root"] = MagicMock()
    repo.account.__dict__["calendar"] = calendar
    inbox = MagicMock()
    inbox.filter.return_value.order_by.return_value = []
    repo.account.__dict__["inbox"] = inbox
    room_calendar = MagicMock()
    room_calendar.all.return_value.only.return_value = []
    room_calendar.view.return_value.only.return_value = []
    # Keep real Account/Calendar construction; fake only the external folder lookup.
    monkeypatch.setattr(
        exchangelib.Account,
        "calendar",
        property(lambda account: calendar if account is repo.account else room_calendar),
    )
    room = room_repository.get_by_id("3.1")
    assert room is not None
    item = exchangelib.CalendarItem(
        account=repo.account,
        folder=calendar,
        id="item-1",
        changekey="change-1",
        uid="uid-1",
        subject="Auto: Algebra",
        start=msk(2026, 9, 11, 10),
        end=msk(2026, 9, 11, 11),
        organizer=exchangelib.Mailbox(email_address=repo.account_email),
        resources=[
            exchangelib.Attendee(
                mailbox=exchangelib.Mailbox(email_address=room.resource_email), response_type="NoResponseReceived"
            )
        ],
        categories=["Auto", "InnoHassleOperation:operation-1"],
        conversation_id=ConversationId(id="conversation-1"),
        datetime_created=msk(2026, 9, 8, 10),
    )
    calendar.get.return_value = item
    calendar.filter.return_value = [item]
    calendar.all.return_value = [item]
    writes = []
    monkeypatch.setattr(exchangelib.CalendarItem, "cancel", lambda self, **kwargs: writes.append((self.id, kwargs)))
    return SimpleNamespace(
        repo=repo, calendar=calendar, inbox=inbox, room_calendar=room_calendar, room=room, item=item, writes=writes
    )


def response(boundary, status, *, associated=True, sender=None, minute=0):
    classes = {"Accept": "Pos", "Tentative": "Tent", "Decline": "Neg"}
    return MeetingResponse(
        id=f"message-{status}",
        item_class=f"IPM.Schedule.Meeting.Resp.{classes[status]}",
        sender=exchangelib.Mailbox(email_address=sender or boundary.room.resource_email),
        associated_calendar_item_id=AssociatedCalendarItemId(id=boundary.item.id) if associated else None,
        conversation_id=ConversationId(id="conversation-1"),
        text_body=f"Room says {status}",
        datetime_received=msk(2026, 9, 8, 11, minute),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["Accept", "Tentative", "Decline"])
async def test_early_response_recovered_without_notification(exchange_boundary, status):
    b = exchange_boundary
    b.inbox.filter.return_value.order_by.return_value = [response(b, status, associated=False)]
    booking, body = await b.repo._confirm_booking(room=b.room, item_id=b.item.id, wait_before_poll=False, timeout_s=0)
    assert booking.room_response == status
    assert booking.room_presence == "unknown"
    assert booking.uid == "uid-1"
    assert body == f"Room says {status}"
    assert b.writes == []


@pytest.mark.asyncio
async def test_confirmation_timeout_retains_request(exchange_boundary):
    b = exchange_boundary
    booking, _ = await b.repo._confirm_booking(room=b.room, item_id=b.item.id, wait_before_poll=False, timeout_s=0)
    assert booking.outlook_booking_id == "item-1"
    assert booking.room_response == "NoResponseReceived"
    assert booking.room_presence == "unknown"
    assert b.writes == []


@pytest.mark.asyncio
@pytest.mark.parametrize("final", ["Accept", "Decline"])
async def test_reconcile_newest_response_supersedes_tentative(exchange_boundary, final):
    b = exchange_boundary
    b.inbox.filter.return_value.order_by.return_value = [
        response(b, final, minute=10),
        response(b, final, minute=10),
        response(b, "Tentative"),
    ]
    b.room_calendar.all.return_value.only.return_value = [SimpleNamespace(uid="uid-1", subject="Renamed by room")]
    result = await b.repo.reconcile_booking(ReconcileBookingEntry(operation_id="operation-1", room_id=b.room.id))
    assert result.room_response == final
    assert result.room_presence == "present"
    assert result.organizer_presence == "present"
    assert result.message_body == f"Room says {final}"
    assert b.writes == []


@pytest.mark.asyncio
async def test_inbox_failure_keeps_attendee_response_and_checks_room(exchange_boundary):
    b = exchange_boundary
    b.item.resources[0].response_type = "Tentative"
    b.inbox.filter.side_effect = exchangelib.errors.ErrorTimeoutExpired("Inbox unavailable")
    b.room_calendar.all.return_value.only.return_value = [SimpleNamespace(uid="uid-1")]
    result = await b.repo.reconcile_booking(ReconcileBookingEntry(operation_id="operation-1", room_id=b.room.id))
    assert result.status == "error"
    assert result.room_response == "Tentative"
    assert result.organizer_presence == "present"
    assert result.room_presence == "present"
    assert result.error
    assert b.writes == []


@pytest.mark.asyncio
async def test_unrelated_sender_and_conversation_not_correlated(exchange_boundary):
    b = exchange_boundary
    wrong_sender = response(b, "Decline", sender="someone@innopolis.ru")
    wrong_identity = response(b, "Decline", associated=False)
    wrong_identity.conversation_id = ConversationId(id="other-conversation")
    b.inbox.filter.return_value.order_by.return_value = [wrong_sender, wrong_identity]
    booking, _ = await b.repo._confirm_booking(room=b.room, item_id=b.item.id, wait_before_poll=False, timeout_s=0)
    assert booking.room_response == "NoResponseReceived"
    assert b.writes == []


@pytest.mark.asyncio
async def test_poller_delivers_on_owning_loop(exchange_boundary):
    b = exchange_boundary
    message = response(b, "Accept")
    b.repo._inbox_pull_subscription_id = "subscription"
    b.repo._inbox_pull_watermark = "watermark"
    b.inbox.get_events.return_value = [
        SimpleNamespace(
            events=[SimpleNamespace(item_id=SimpleNamespace(id=message.id, changekey="m-change"), watermark="next")],
            more_events=False,
        )
    ]
    b.inbox.get.return_value = message
    wait = exchange_module._RoomWait(
        room_email=b.room.resource_email, calendar_item=b.item, loop=asyncio.get_running_loop()
    )
    b.repo._room_waits[b.item.id] = wait
    await asyncio.to_thread(b.repo._inbox_poll_step)
    await asyncio.wait_for(wait.event.wait(), 1)
    assert wait.result is not None
    assert wait.result[0] == "Accept"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [exchangelib.errors.ErrorAccessDenied("denied"), exchangelib.errors.ErrorExceededFindCountLimit("limit")]
)
async def test_room_read_failure_is_unknown_not_absent(exchange_boundary, error):
    b = exchange_boundary
    b.room_calendar.all.side_effect = error
    result = await b.repo.reconcile_booking(ReconcileBookingEntry(uid="uid-1", room_id=b.room.id))
    assert result.status == "error"
    assert result.organizer_presence == "present"
    assert result.room_presence == "unknown"
    assert result.error


@pytest.mark.asyncio
async def test_stale_item_id_is_not_proof_of_cancellation(exchange_boundary):
    b = exchange_boundary
    b.calendar.get.side_effect = exchangelib.errors.ErrorItemNotFound("stale id")
    result = await b.repo.reconcile_booking(ReconcileBookingEntry(outlook_booking_id="stale", room_id=b.room.id))
    assert result.organizer_presence == "unknown"
    assert result.room_presence == "unknown"


@pytest.mark.asyncio
async def test_cancel_validates_room_before_writing(exchange_boundary):
    b = exchange_boundary
    b.item.resources = []
    with pytest.raises(HTTPException, match="requested room"):
        await b.repo.cancel_scoped_booking(ScopedCancelBookingRequest(uid="uid-1", room_id=b.room.id, scope="series"))
    assert b.writes == []


@pytest.mark.asyncio
async def test_cancel_series_waits_for_room_propagation(exchange_boundary, monkeypatch):
    b = exchange_boundary
    b.item.type = "RecurringMaster"
    b.room_calendar.all.return_value.only.return_value = [SimpleNamespace(uid="uid-1")]

    def cancel(item, **kwargs):
        b.writes.append(item.id)
        b.calendar.filter.return_value = []
        b.calendar.all.return_value = []

    monkeypatch.setattr(exchangelib.CalendarItem, "cancel", cancel)
    result = await b.repo.cancel_scoped_booking(
        ScopedCancelBookingRequest(uid="uid-1", room_id=b.room.id, scope="series")
    )
    assert b.writes == ["item-1"]
    assert result.organizer_presence == "absent"
    assert result.room_presence == "present"
    assert result.cancellation_status == "cancelling"


@pytest.mark.asyncio
async def test_cancel_exact_occurrence_does_not_cancel_master(exchange_boundary, monkeypatch):
    b = exchange_boundary
    b.item.type = "RecurringMaster"
    occurrence = exchangelib.CalendarItem(
        account=b.repo.account,
        id="occurrence-1",
        uid=b.item.uid,
        type="Occurrence",
        start=b.item.start,
        end=b.item.end,
    )
    b.calendar.view.return_value = [occurrence]

    def cancel(item, **kwargs):
        b.writes.append(item.id)
        b.calendar.view.return_value = []

    monkeypatch.setattr(exchangelib.CalendarItem, "cancel", cancel)
    result = await b.repo.cancel_scoped_booking(
        ScopedCancelBookingRequest(
            uid="uid-1",
            room_id=b.room.id,
            scope="occurrence",
            start=b.item.start,
            end=b.item.end,
        )
    )
    assert b.writes == ["occurrence-1"]
    assert result.cancellation_status == "cancelled"


@pytest.mark.asyncio
@pytest.mark.parametrize("room_present", [False, True])
async def test_repeat_occurrence_cancellation_never_changes_master(exchange_boundary, room_present):
    b = exchange_boundary
    b.item.type = "RecurringMaster"
    b.calendar.view.return_value = []
    b.room_calendar.view.return_value.only.return_value = (
        [SimpleNamespace(uid=b.item.uid, start=b.item.start, end=b.item.end)] if room_present else []
    )
    result = await b.repo.cancel_scoped_booking(
        ScopedCancelBookingRequest(
            operation_id="operation-1",
            room_id=b.room.id,
            scope="occurrence",
            start=b.item.start,
            end=b.item.end,
        )
    )
    assert result.cancellation_status == ("requires_review" if room_present else "cancelled")
    assert result.organizer_presence == "absent"
    assert b.writes == []
    assert b.calendar.filter.return_value == [b.item]


@pytest.mark.asyncio
@pytest.mark.parametrize("applied", [False, True])
async def test_cancel_unknown_send_reconciles_without_retry(exchange_boundary, monkeypatch, applied):
    b = exchange_boundary

    def cancel(item, **kwargs):
        b.writes.append(item.id)
        if applied:
            b.calendar.filter.return_value = []
            b.calendar.all.return_value = []
        raise TimeoutError("Simulated uncertain external cancellation")

    monkeypatch.setattr(exchangelib.CalendarItem, "cancel", cancel)
    result = await b.repo.cancel_scoped_booking(
        ScopedCancelBookingRequest(operation_id="operation-1", room_id=b.room.id, scope="series")
    )
    assert result.cancellation_status == ("cancelled" if applied else "requires_review")
    assert b.writes == ["item-1"]
    assert any("TimeoutError" in evidence for evidence in result.evidence)


@pytest.mark.asyncio
async def test_restart_recovers_operation_marker_without_invitation(exchange_boundary):
    b = exchange_boundary
    b.item.resources[0].response_type = "Tentative"
    booking = await b.repo.create_booking(
        room=b.room,
        start=b.item.start,
        end=b.item.end,
        title="Algebra",
        participant_emails=[],
        operation_id="operation-1",
    )
    assert booking.outlook_booking_id == "item-1"
    assert booking.operation_id == "operation-1"
    assert booking.room_response == "Tentative"
    b.calendar.bulk_create.assert_not_called()


@pytest.mark.asyncio
async def test_partial_bulk_persists_marker_and_streams_known_ids(exchange_boundary, monkeypatch):
    b = exchange_boundary
    b.calendar.filter.return_value = []
    b.calendar.bulk_create.return_value = [SimpleNamespace(id="item-1", changekey="change-1"), ValueError("bad item")]
    b.item.resources[0].response_type = "Tentative"
    monkeypatch.setattr(exchangelib.CalendarItem, "save", lambda self, **kwargs: b.writes.append((self.id, kwargs)))
    entries = [
        BmpBatchCreateEntry(
            room=b.room,
            start=b.item.start,
            end=b.item.end,
            title="Algebra",
            participant_emails=[],
            operation_id=f"operation-{i}",
        )
        for i in (1, 2)
    ]
    events = [event async for event in b.repo.iter_create_bookings_batch(entries)]
    assert len(b.calendar.bulk_create.call_args.args[0]) == 2
    assert b.calendar.bulk_create.call_args.kwargs["send_meeting_invitations"] == "SendToNone"
    assert "InnoHassleOperation:operation-1" in b.calendar.bulk_create.call_args.args[0][0].categories
    assert entries[0].sent_booking is not None
    assert entries[0].sent_booking.outlook_booking_id == "item-1"
    assert any(event[2] == [0] for event in events)
    assert any(event[0] == 1 and event[1].status == "error" for event in events)
    assert any(event[0] == 0 and event[1].booking.room_response == "Tentative" for event in events)


@pytest.mark.asyncio
async def test_ambiguous_create_not_retried(exchange_boundary):
    b = exchange_boundary
    b.calendar.filter.return_value = []
    b.calendar.bulk_create.side_effect = TimeoutError("unknown save outcome")
    entry = BmpBatchCreateEntry(
        room=b.room,
        start=b.item.start,
        end=b.item.end,
        title="Algebra",
        participant_emails=[],
        operation_id="operation-1",
    )
    first = [event async for event in b.repo.iter_create_bookings_batch([entry])]
    second = [event async for event in b.repo.iter_create_bookings_batch([entry])]
    assert first[0][1].booking.room_response == "Unknown"
    assert second[0][1].status == "error"
    assert "unknown" in second[0][1].error
    assert b.calendar.bulk_create.call_count == 1


@pytest.mark.asyncio
async def test_same_slot_distinct_source_meetings_survive_merge(exchange_boundary):
    b = exchange_boundary
    start, end = b.item.start, b.item.end
    first = b.repo.booking_from_calendar_item(b.item, room_id=b.room.id)
    second = first.model_copy(update={"outlook_booking_id": "item-2", "uid": "uid-2"})
    busy = first.model_copy(
        update={
            "source": "free_busy",
            "uid": None,
            "outlook_booking_id": None,
            "outlook_entry_id": "room-entry",
            "busy_type": "Tentative",
        }
    )
    await b.repo._cache_from_account_calendar.update_cache(b.room.id, [first, second], start, end)
    await b.repo._cache_from_busy_info.update_cache(b.room.id, [busy], start, end)
    bookings = await b.repo.get_bookings_for_room(b.room.id, start, end)
    assert len(bookings) == 3
    assert len({booking.id for booking in bookings}) == 3
    assert any(booking.busy_type == "Tentative" for booking in bookings)


def test_reconcile_route_returns_structured_evidence(
    exchange_boundary, room_booking_client, api_key_headers, monkeypatch
):
    from src.room_booking.modules.bmp import routes

    b = exchange_boundary
    monkeypatch.setattr(routes, "bmp_repository", b.repo)
    result = room_booking_client.post(
        "/bmp/auto-bookings/reconcile",
        headers=api_key_headers,
        json={"entries": [{"operation_id": "operation-1", "room_id": b.room.id}]},
    )
    assert result.status_code == 200
    evidence = result.json()[0]
    assert evidence["organizer_presence"] == "present"
    assert evidence["room_presence"] == "absent"
    assert evidence["booking"]["operation_id"] == "operation-1"
    assert evidence["checked_at"]
    assert evidence["evidence"]


def test_cancel_route_requires_explicit_scope(exchange_boundary, room_booking_client, api_key_headers):
    result = room_booking_client.post(
        "/bmp/auto-bookings/cancel",
        headers=api_key_headers,
        json={
            "uid": "uid-1",
            "room_id": exchange_boundary.room.id,
        },
    )
    assert result.status_code == 422
    assert exchange_boundary.writes == []


@pytest.mark.asyncio
async def test_same_operation_concurrent_calls_create_once(exchange_boundary, monkeypatch):
    b = exchange_boundary
    b.calendar.filter.return_value = []
    b.item.resources[0].response_type = "Tentative"

    def create(items, **kwargs):
        b.calendar.filter.return_value = [b.item]
        return [SimpleNamespace(id=b.item.id, changekey=b.item.changekey)]

    b.calendar.bulk_create.side_effect = create
    monkeypatch.setattr(exchangelib.CalendarItem, "save", lambda self, **kwargs: b.writes.append(self.id))

    async def run():
        return await b.repo.create_booking(
            room=b.room,
            start=b.item.start,
            end=b.item.end,
            title="Algebra",
            participant_emails=[],
            operation_id="operation-1",
        )

    results = await asyncio.gather(run(), run())
    assert [booking.outlook_booking_id for booking in results] == ["item-1", "item-1"]
    assert b.calendar.bulk_create.call_count == 1
    assert b.writes == ["item-1"]


@pytest.mark.asyncio
async def test_duplicate_operation_in_single_batch_never_double_sends(exchange_boundary, monkeypatch):
    b = exchange_boundary
    b.calendar.filter.return_value = []
    b.calendar.bulk_create.return_value = [SimpleNamespace(id="item-1", changekey="change-1")]
    b.item.resources[0].response_type = "Tentative"
    monkeypatch.setattr(exchangelib.CalendarItem, "save", lambda self, **kwargs: b.writes.append(self.id))
    entry = BmpBatchCreateEntry(
        room=b.room,
        start=b.item.start,
        end=b.item.end,
        title="Algebra",
        participant_emails=[],
        operation_id="operation-1",
    )
    events = [event async for event in b.repo.iter_create_bookings_batch([entry, entry.model_copy()])]
    assert len(b.calendar.bulk_create.call_args.args[0]) == 1
    assert any(event[0] == 1 and event[1].status == "error" for event in events)
    assert b.writes == ["item-1"]


@pytest.mark.asyncio
async def test_cross_mailbox_identity_cannot_cancel(exchange_boundary):
    b = exchange_boundary
    with pytest.raises(HTTPException, match="mailbox"):
        await b.repo.cancel_scoped_booking(
            ScopedCancelBookingRequest(
                uid="uid-1",
                room_id=b.room.id,
                organizer_mailbox="other@innopolis.ru",
                scope="series",
            )
        )
    assert b.writes == []


@pytest.mark.asyncio
async def test_recent_cancellation_does_not_hide_fetched_conflict(exchange_boundary):
    b = exchange_boundary
    booking = b.repo.booking_from_calendar_item(b.item, room_id=b.room.id)
    await b.repo._cache_from_account_calendar.update_cache(b.room.id, [booking], b.item.start, b.item.end)
    await b.repo._cache_from_busy_info.update_cache(b.room.id, [], b.item.start, b.item.end)
    await b.repo._recently.mark_canceled(b.item.id)
    result = await b.repo.get_bookings_for_room(b.room.id, b.item.start, b.item.end)
    assert len(result) == 1
    assert result[0].outlook_booking_id == b.item.id


@pytest.mark.asyncio
async def test_saved_request_with_response_read_failure_keeps_identity(exchange_boundary, monkeypatch):
    b = exchange_boundary

    def save(item, **kwargs):
        item.id = "saved-id"
        item.changekey = "saved-change"

    monkeypatch.setattr(exchangelib.CalendarItem, "save", save)
    b.calendar.get.side_effect = exchangelib.errors.ErrorAccessDenied("unavailable")
    booking = await exchange_module.ExchangeBookingRepository.create_booking(
        b.repo,
        room=b.room,
        start=b.item.start,
        end=b.item.end,
        title="Meeting",
        participant_emails=[],
    )
    assert booking.outlook_booking_id == "saved-id"
    assert booking.room_response == "Unknown"
    assert b.writes == []


@pytest.mark.asyncio
async def test_unavailable_free_busy_never_means_free(exchange_boundary):
    b = exchange_boundary
    protocol = MagicMock()
    protocol.get_free_busy_info.return_value = [SimpleNamespace(view_type="None", calendar_events=None)]
    b.repo.account.protocol = protocol
    with pytest.raises(HTTPException, match="availability unavailable"):
        await b.repo._fetch_bookings_from_busy_info([b.room], b.item.start, b.item.end, use_cache=False)


@pytest.mark.asyncio
async def test_free_busy_retains_tentative_and_anonymous_distinct_entries(exchange_boundary):
    b = exchange_boundary
    protocol = MagicMock()
    protocol.get_free_busy_info.return_value = [
        SimpleNamespace(
            view_type="Detailed",
            calendar_events=[
                SimpleNamespace(start=b.item.start, end=b.item.end, details=None, busy_type="Tentative"),
                SimpleNamespace(start=b.item.start, end=b.item.end, details=None, busy_type="Busy"),
            ],
        )
    ]
    b.repo.account.protocol = protocol
    result = await b.repo._fetch_bookings_from_busy_info([b.room], b.item.start, b.item.end, use_cache=False)
    bookings = result[b.room.id]
    assert len(bookings) == 2
    assert bookings[0].busy_type == "Tentative"
    assert bookings[0].id != bookings[1].id
