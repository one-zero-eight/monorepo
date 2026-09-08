"""BMP Specialist calendar — dedicated mailbox, default calendar, Auto-tagged events."""

# ruff: noqa: BLE001
import asyncio
import datetime as dtm
import time as tm
from collections.abc import AsyncIterator, Iterable
from typing import Any, Literal, Protocol, cast

import exchangelib
from exchangelib import Q
from exchangelib.errors import ErrorItemNotFound
from exchangelib.items import MOVE_TO_DELETED_ITEMS, SEND_TO_ALL_AND_SAVE_COPY
from exchangelib.recurrence import Recurrence
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.inh_accounts_sdk import UserSchema
from src.logging_ import logger
from src.room_booking.config import settings
from src.room_booking.config_schema import Room
from src.room_booking.modules.bookings.exchange_repository import ExchangeBookingRepository
from src.room_booking.modules.bookings.schemas import (
    Booking,
    BookingStatus,
    Presence,
    ReconcileBookingEntry,
    ReconcileBookingResult,
    ScopedCancelBookingRequest,
)
from src.room_booking.modules.bookings.service import get_emails_to_attendees_index
from src.room_booking.modules.bookings.tz_utils import to_msk
from src.room_booking.modules.rooms.repository import room_repository

AUTO_SUBJECT_PREFIX = "Auto: "
AUTO_CATEGORY = "Auto"
BMP_CREATE_CHUNK_SIZE = 16
BMP_CANCEL_CHUNK_SIZE = 8

_AUTO_FIND_FIELDS = (
    "id",
    "changekey",
    "subject",
    "start",
    "end",
    "categories",
    "required_attendees",
    "resources",
    "recurrence",
    "uid",
    "type",
    "organizer",
)


class _CalendarItemWindowFields(Protocol):
    start: Any
    end: Any
    recurrence: Any


def _as_window_datetime(
    value: dtm.date | dtm.datetime,
    *,
    clock: dtm.time,
    tzinfo: dtm.tzinfo | None,
) -> dtm.datetime:
    if isinstance(value, dtm.datetime):
        return to_msk(value)
    return dtm.datetime.combine(value, clock, tzinfo=tzinfo)


def auto_item_overlaps_window(
    item: _CalendarItemWindowFields,
    window_start: dtm.datetime,
    window_end: dtm.datetime,
) -> bool:
    item_start = to_msk(cast(dtm.datetime, item.start))
    item_end = to_msk(cast(dtm.datetime, item.end))
    recurrence = item.recurrence
    boundary = getattr(recurrence, "boundary", None) if recurrence is not None else None
    if boundary is None:
        return item_start < window_end and item_end > window_start

    tzinfo = item_start.tzinfo
    series_start = getattr(boundary, "start", None)
    range_start = (
        _as_window_datetime(series_start, clock=item_start.time(), tzinfo=tzinfo)
        if series_start is not None
        else item_start
    )
    series_end = getattr(boundary, "end", None)
    if series_end is None:
        return range_start < window_end
    range_end = _as_window_datetime(series_end, clock=item_end.time(), tzinfo=tzinfo)
    return range_start < window_end and range_end > window_start


class BmpBatchCreateEntry(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    room: Room
    start: dtm.datetime
    end: dtm.datetime
    title: str
    participant_emails: list[str]
    recurrence: Recurrence | None = None
    categories: list[str] | None = None
    description: str | None = None
    operation_id: str | None = None
    sent_booking: Booking | None = Field(default=None, exclude=True)
    send_error: str | None = Field(default=None, exclude=True)


class BmpBatchItemResult(BaseModel):
    status: Literal["ok", "error"]
    booking: Booking | None = None
    error: str | None = None
    message_body: str | None = None


class CancelAllAutoBookingsResult(BaseModel):
    cancelled: list[str]
    failed: dict[str, str]


class BmpCalendarRepository(ExchangeBookingRepository):
    """BMP bookings on the account default calendar, marked with Auto subject prefix and category."""

    @staticmethod
    def _operation_marker(operation_id: str) -> str:
        return f"InnoHassleOperation:{operation_id}"

    def _find_identity_items(self, entry: ReconcileBookingEntry) -> list[exchangelib.CalendarItem]:
        if entry.organizer_mailbox and entry.organizer_mailbox.lower() != self.account_email.lower():
            raise HTTPException(409, "Organizer mailbox does not match BMP mailbox")
        # Search durable identifiers independently of a stale item ID.
        if entry.operation_id:
            marker = self._operation_marker(entry.operation_id)
            items = [
                item
                for item in self.selected_calendar.filter(categories__contains=marker)
                if marker in (item.categories or [])
            ]
        elif entry.uid:
            # Calendar UID is not an EWS-searchable field. FindItem paginates
            # masters without expanding the whole semester CalendarView.
            items = [item for item in self.selected_calendar.all() if item.uid == entry.uid]
        elif entry.outlook_booking_id:
            try:
                items = [self.selected_calendar.get(id=entry.outlook_booking_id)]
            except ErrorItemNotFound:
                items = []
        else:
            raise HTTPException(400, "An operation_id, uid or outlook_booking_id is required")
        for item in items:
            if not isinstance(item, exchangelib.CalendarItem) or not self._is_auto_calendar_item(item):
                raise HTTPException(409, "Identity does not belong to an Auto calendar item")
            if entry.uid and item.uid != entry.uid:
                raise HTTPException(409, "UID does not match the operation")
            organizer = item.organizer
            if not organizer or str(organizer.email_address).lower() != self.account_email.lower():
                raise HTTPException(409, "Item is not organized by the BMP mailbox")
            room = room_repository.get_by_id(entry.room_id)
            if room is None or room.resource_email not in get_emails_to_attendees_index(item):
                raise HTTPException(409, "Item does not invite the requested room")
        if len(items) > 1:
            raise HTTPException(409, "Ambiguous Exchange identity; manual review required")
        return items

    def _room_calendar(self, room: Room) -> exchangelib.folders.Calendar:
        room_account = exchangelib.Account(
            room.resource_email,
            autodiscover=False,
            access_type=exchangelib.DELEGATE,
            config=self.account.protocol.config,
        )
        return cast(exchangelib.folders.Calendar, room_account.calendar)

    def _read_room_presence(
        self, room: Room, uid: str | None, start: dtm.datetime | None, end: dtm.datetime | None, scope: str
    ) -> tuple[str, list[str]]:
        if not uid:
            return "unknown", ["Room lookup requires a UID; slot/title matching is not identity"]
        calendar = self._room_calendar(room)
        if scope == "occurrence":
            if start is None or end is None or start >= end:
                raise HTTPException(400, "Occurrence lookup requires a valid start/end window")
            items = list(
                calendar.view(
                    exchangelib.EWSDateTime.from_datetime(to_msk(start)),
                    exchangelib.EWSDateTime.from_datetime(to_msk(end)),
                ).only("uid", "start", "end", "id")
            )
            matches = [item for item in items if item.uid == uid and item.start == start and item.end == end]
            return ("present" if matches else "absent"), ["Complete room occurrence window read by UID and time"]
        items = [item for item in calendar.all().only("uid", "id", "type") if item.uid == uid]
        # A master proves series identity exists, not coverage of every occurrence.
        return ("present" if items else "absent"), [
            "Complete room UID lookup; series presence is not occurrence coverage"
        ]

    async def reconcile_booking(self, entry: ReconcileBookingEntry) -> ReconcileBookingResult:
        result = ReconcileBookingResult(
            operation_id=entry.operation_id,
            outlook_booking_id=entry.outlook_booking_id,
            uid=entry.uid,
            organizer_mailbox=self.account_email,
            room_id=entry.room_id,
            checked_at=dtm.datetime.now(dtm.UTC),
        )
        room = room_repository.get_by_id(entry.room_id)
        if room is None:
            result.status, result.error = "error", "Room not found"
            return result
        try:
            items = await asyncio.to_thread(self._find_identity_items, entry)
            if items:
                item = items[0]
                result.organizer_presence = "present"
                result.outlook_booking_id = str(item.id)
                result.uid = cast(str | None, item.uid)
                result.booking = self.booking_from_calendar_item(item, room_id=room.id)
                result.evidence.append("Organizer item found by durable identity")
                if entry.scope == "occurrence":
                    if entry.start is None or entry.end is None or entry.start >= entry.end:
                        raise HTTPException(400, "Occurrence lookup requires a valid start/end window")
                    occurrences = await asyncio.to_thread(
                        lambda: list(
                            self.selected_calendar.view(
                                exchangelib.EWSDateTime.from_datetime(entry.start),
                                exchangelib.EWSDateTime.from_datetime(entry.end),
                            )
                        )
                    )
                    result.organizer_presence = (
                        "present"
                        if any(
                            occurrence.uid == result.uid
                            and occurrence.start == entry.start
                            and occurrence.end == entry.end
                            for occurrence in occurrences
                        )
                        else "absent"
                    )
                    result.evidence.append("Complete organizer occurrence window read by UID and time")
                response = result.booking.room_response if result.booking else None
                body = None
                try:
                    response, _, body = await asyncio.to_thread(self._recover_room_response, item, room.resource_email)
                except Exception as exc:
                    result.status = "error"
                    result.error = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
                    result.evidence.append(
                        "Response history read failed; retaining attendee response and checking room"
                    )
                result.room_response = cast(BookingStatus, response or "Unknown")
                result.message_body = body
                if item.meeting_request_was_sent is not True and response not in ("Accept", "Tentative", "Decline"):
                    result.room_response = "Unknown"
                    result.evidence.append("Organizer draft exists; invitation send is not verified. Do not resend.")
                if result.booking:
                    result.operation_id = result.booking.operation_id or entry.operation_id
            elif entry.operation_id or entry.uid:
                result.organizer_presence = "absent"
                result.evidence.append("Complete organizer identity lookup returned no items")
            else:
                result.evidence.append("Old item ID not found; organizer absence is not established")
        except Exception as exc:
            result.status = "error"
            result.error = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
            result.evidence.append("Organizer/response lookup failed; do not resend")
            return result
        try:
            presence, evidence = await asyncio.to_thread(
                self._read_room_presence, room, result.uid, entry.start, entry.end, entry.scope
            )
            result.room_presence = cast(Presence, presence)
            result.evidence.extend(evidence)
        except Exception as exc:
            result.status = "error"
            result.error = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
            result.evidence.append("Room calendar read failed or incomplete; presence remains unknown")
        if result.booking:
            result.booking.room_response = result.room_response
            result.booking.room_presence = result.room_presence
            result.booking.message_body = result.message_body
            result.booking.checked_at = result.checked_at
        return result

    async def cancel_scoped_booking(self, entry: ScopedCancelBookingRequest) -> ReconcileBookingResult:
        items = await asyncio.to_thread(self._find_identity_items, entry)
        if not items:
            result = await self.reconcile_booking(entry)
            result.cancellation_status = (
                "cancelled"
                if result.organizer_presence == "absent" and result.room_presence == "absent"
                else "requires_review"
            )
            return result
        item = items[0]
        if entry.scope == "occurrence":
            if entry.start is None or entry.end is None or entry.start >= entry.end:
                raise HTTPException(400, "Occurrence cancellation requires valid start/end")
            occurrences = await asyncio.to_thread(
                lambda: list(
                    self.selected_calendar.view(
                        exchangelib.EWSDateTime.from_datetime(entry.start),
                        exchangelib.EWSDateTime.from_datetime(entry.end),
                    )
                )
            )
            matches = [
                candidate
                for candidate in occurrences
                if candidate.uid == item.uid and candidate.start == entry.start and candidate.end == entry.end
            ]
            if not matches:
                result = await self.reconcile_booking(entry.model_copy(update={"uid": item.uid}))
                result.cancellation_status = (
                    "cancelled"
                    if result.organizer_presence == "absent" and result.room_presence == "absent"
                    else "requires_review"
                )
                result.evidence.append("Exact occurrence absent; no cancellation resent and series unchanged")
                return result
            if len(matches) != 1 or matches[0].type == "RecurringMaster":
                raise HTTPException(409, "Exact occurrence not found; series was not changed")
            item = matches[0]
        elif item.type in ("Occurrence", "Exception"):
            raise HTTPException(409, "Series cancellation requires a master identity")
        uid = cast(str | None, item.uid)
        item_id = str(item.id)
        # Do not use recently-cancelled cache as evidence of successful cancellation.
        try:
            await asyncio.to_thread(item.cancel, new_body=f"Cancelled by BMP; scope={entry.scope}")
        except Exception as exc:
            result = await self.reconcile_booking(entry.model_copy(update={"uid": uid}))
            result.cancellation_status = (
                "cancelled"
                if result.organizer_presence == "absent" and result.room_presence == "absent"
                else "requires_review"
            )
            result.evidence.append(f"Cancellation send raised {type(exc).__name__}; reconciled without retry")
            return result
        result = await self.reconcile_booking(entry.model_copy(update={"uid": uid}))
        if entry.scope == "occurrence" and result.organizer_presence == "present":
            # The master remains after deleting one occurrence. Verify only that occurrence.
            try:
                remaining = await asyncio.to_thread(
                    lambda: list(
                        self.selected_calendar.view(
                            exchangelib.EWSDateTime.from_datetime(entry.start),
                            exchangelib.EWSDateTime.from_datetime(entry.end),
                        )
                    )
                )
                result.organizer_presence = (
                    "present"
                    if any(
                        candidate.uid == uid and candidate.start == entry.start and candidate.end == entry.end
                        for candidate in remaining
                    )
                    else "absent"
                )
            except Exception as exc:
                result.organizer_presence, result.status, result.error = "unknown", "error", str(exc)
        result.cancellation_status = (
            "cancelled" if result.organizer_presence == "absent" and result.room_presence == "absent" else "cancelling"
        )
        result.evidence.append("Cancellation sent; room propagation may be delayed")
        if result.cancellation_status == "cancelled":
            await self._recently.mark_canceled(item_id)
        return result

    async def create_booking(
        self,
        room: Room,
        start: dtm.datetime,
        end: dtm.datetime,
        title: str,
        participant_emails: list[str],
        organizer: UserSchema | None = None,
        recurrence: Recurrence | None = None,
        categories: list[str] | None = None,
        description: str | None = None,
        operation_id: str | None = None,
    ) -> Booking:
        entry = BmpBatchCreateEntry(
            room=room,
            start=start,
            end=end,
            title=title,
            participant_emails=participant_emails,
            recurrence=recurrence,
            categories=categories,
            description=description,
            operation_id=operation_id,
        )
        async for _, result, _ in self.iter_create_bookings_batch([entry]):
            if result is None:
                continue
            if result.status == "ok" and result.booking is not None:
                return result.booking
            raise HTTPException(
                502,
                {
                    "message": result.error or "Exchange outcome unknown; reconcile before retrying",
                    "booking": result.booking.model_dump(mode="json") if result.booking else None,
                    "operation_id": operation_id,
                },
            )
        raise HTTPException(502, "Exchange returned no booking result")

    @staticmethod
    def _auto_subject(title: str) -> str:
        if title.startswith(AUTO_SUBJECT_PREFIX):
            return title
        return f"{AUTO_SUBJECT_PREFIX}{title}"

    @staticmethod
    def _auto_categories(categories: list[str] | None) -> list[str]:
        rest = [c for c in (categories or []) if c != AUTO_CATEGORY]
        return [AUTO_CATEGORY, *rest]

    @staticmethod
    def _is_auto_calendar_item(item: exchangelib.CalendarItem) -> bool:
        subject = cast(str, item.subject or "")
        if subject.startswith(AUTO_SUBJECT_PREFIX):
            return True
        return AUTO_CATEGORY in list(cast(Iterable[str], item.categories or []))

    def _build_calendar_item(
        self,
        *,
        room: Room,
        start: dtm.datetime,
        end: dtm.datetime,
        title: str,
        participant_emails: list[str],
        organizer: UserSchema | None = None,
        recurrence: Recurrence | None = None,
        categories: list[str] | None = None,
        description: str | None = None,
        operation_id: str | None = None,
        **kwargs,
    ) -> exchangelib.CalendarItem:
        categories = list(categories or [])
        if operation_id:
            categories.append(self._operation_marker(operation_id))
        return super()._build_calendar_item(
            room=room,
            start=start,
            end=end,
            title=self._auto_subject(title),
            participant_emails=participant_emails,
            organizer=organizer,
            recurrence=recurrence,
            categories=self._auto_categories(categories),
            description=description,
            **kwargs,
        )

    def _create_booking_description(
        self,
        *,
        room: Room,
        participant_emails: list[str],
        organizer: UserSchema | None = None,
        description: str | None = None,
        **kwargs,
    ) -> str:
        footer = (
            f"Booking on behalf of BMP Specialist ({self.account_email})\n"
            f"Provider: https://innohassle.ru/room-booking\n"
            f"\n"
            f"View full room schedule at https://innohassle.ru/room-booking/rooms/{room.id}"
        )
        extra = (description or "").strip()
        if extra:
            return f"{extra}\n\n{footer}"
        return footer

    def _auto_find_items(self, *fields: str) -> list[exchangelib.CalendarItem]:
        return list(
            self.selected_calendar.filter(
                Q(categories__contains=AUTO_CATEGORY) | Q(subject__startswith=AUTO_SUBJECT_PREFIX)
            ).only(*fields)
        )

    def _list_auto_chain_items(
        self,
    ) -> list[exchangelib.CalendarItem]:
        return self._auto_find_items("id", "changekey", "subject", "organizer", "categories")

    async def _list_auto_calendar_items(
        self,
        start: dtm.datetime,
        end: dtm.datetime,
    ) -> list[exchangelib.CalendarItem]:
        start_msk = to_msk(start)
        end_msk = to_msk(end)

        def _fetch() -> list[exchangelib.CalendarItem]:
            return [
                item
                for item in self._auto_find_items(*_AUTO_FIND_FIELDS)
                if self._is_auto_calendar_item(item) and auto_item_overlaps_window(item, start_msk, end_msk)
            ]

        return await asyncio.to_thread(_fetch)

    async def list_auto_bookings(
        self,
        start: dtm.datetime,
        end: dtm.datetime,
    ) -> list[Booking]:
        bookings: list[Booking] = []
        for item in await self._list_auto_calendar_items(start, end):
            if booking := self.booking_from_calendar_item(item, room_id=None):
                bookings.append(booking)
        logger.info(f"Found {len(bookings)} auto bookings in BMP calendar")
        return bookings

    async def cancel_all_auto_bookings(self) -> CancelAllAutoBookingsResult:
        items = await asyncio.to_thread(self._list_auto_chain_items)
        result = await self._bulk_cancel_auto_items(items)
        logger.info(f"Canceled {len(result.cancelled)}/{len(result.cancelled) + len(result.failed)} auto bookings")
        return result

    async def _bulk_cancel_auto_items(
        self,
        items: list[exchangelib.CalendarItem],
    ) -> CancelAllAutoBookingsResult:
        cancelled: list[str] = []
        failed: dict[str, str] = {}

        for offset in range(0, len(items), BMP_CANCEL_CHUNK_SIZE):
            chunk = items[offset : offset + BMP_CANCEL_CHUNK_SIZE]
            try:
                results = await asyncio.to_thread(
                    self.account.bulk_delete,
                    ids=chunk,
                    delete_type=MOVE_TO_DELETED_ITEMS,
                    send_meeting_cancellations=SEND_TO_ALL_AND_SAVE_COPY,
                    chunk_size=BMP_CANCEL_CHUNK_SIZE,
                )
            except Exception as e:
                for item in chunk:
                    item_id = str(item.id)
                    if await self.get_booking(item_id) is None:
                        await self._recently.mark_canceled(item_id)
                        cancelled.append(item_id)
                    else:
                        failed[item_id] = str(e)
                continue
            for item, delete_result in zip(chunk, results, strict=True):
                item_id = str(item.id)
                if delete_result is True or isinstance(delete_result, ErrorItemNotFound):
                    await self._recently.mark_canceled(item_id)
                    cancelled.append(item_id)
                    continue
                failed[item_id] = str(delete_result)

        return CancelAllAutoBookingsResult(cancelled=cancelled, failed=failed)

    async def cancel_bookings_batch(
        self,
        outlook_booking_ids: list[str],
        *,
        email: str | None = None,
    ) -> CancelAllAutoBookingsResult:
        if not outlook_booking_ids:
            return CancelAllAutoBookingsResult(cancelled=[], failed={})

        booking_ids = list(dict.fromkeys(outlook_booking_ids))
        cancelled: list[str] = []
        failed: dict[str, str] = {}
        items: list[exchangelib.CalendarItem] = []

        for booking_id in booking_ids:
            if await self._recently.is_canceled(booking_id):
                cancelled.append(booking_id)
                continue
            item = await self.get_booking(booking_id)
            if item is None:
                await self._recently.mark_canceled(booking_id)
                cancelled.append(booking_id)
                continue
            if not self._is_auto_calendar_item(item):
                failed[booking_id] = "Booking is not an Auto booking"
                continue
            items.append(item)

        bulk_result = await self._bulk_cancel_auto_items(items)
        cancelled.extend(bulk_result.cancelled)
        failed.update(bulk_result.failed)

        result = CancelAllAutoBookingsResult(cancelled=cancelled, failed=failed)
        logger.info(f"Batch canceled {len(result.cancelled)}/{len(booking_ids)} auto bookings (email={email})")
        return result

    async def cancel_auto_booking_by_slot(
        self,
        *,
        room_id: str,
        start: dtm.datetime,
        end: dtm.datetime,
        title: str,
        email: str | None = None,
    ) -> bool:
        start_msk = to_msk(start)
        end_msk = to_msk(end)
        title_normalized = title.strip()
        window_start = start_msk - dtm.timedelta(hours=2)
        window_end = end_msk + dtm.timedelta(hours=2)

        def _fetch_slot_occurrences() -> list[exchangelib.CalendarItem]:
            items = self.selected_calendar.view(
                exchangelib.EWSDateTime.from_datetime(window_start),
                exchangelib.EWSDateTime.from_datetime(window_end),
            ).only(*_AUTO_FIND_FIELDS)
            return [item for item in items if self._is_auto_calendar_item(item)]

        for item in await asyncio.to_thread(_fetch_slot_occurrences):
            booking = self.booking_from_calendar_item(item, room_id=room_id)
            if booking is None:
                continue
            if booking.room_id != room_id:
                continue
            if to_msk(booking.start) != start_msk or to_msk(booking.end) != end_msk:
                continue
            if booking.title.strip() != title_normalized:
                continue
            await self.cancel_booking(item, email=email)
            return True
        return False

    async def iter_create_bookings_batch(
        self, entries: list[BmpBatchCreateEntry]
    ) -> AsyncIterator[tuple[int | None, BmpBatchItemResult | None, list[int] | None]]:
        t_batch = tm.monotonic()
        if not entries:
            return
        for offset in range(0, len(entries), BMP_CREATE_CHUNK_SIZE):
            chunk = entries[offset : offset + BMP_CREATE_CHUNK_SIZE]
            async for local_index, result, sent_indexes in self._iter_create_bookings_chunk(chunk):
                if sent_indexes is not None:
                    yield (None, None, [offset + index for index in sent_indexes])
                    continue
                if local_index is None:
                    continue
                yield (offset + local_index, result, None)
        logger.info(f"create_bookings_batch: finished {len(entries)} entries in {tm.monotonic() - t_batch:.3f}s")

    async def _iter_create_bookings_chunk(
        self, entries: list[BmpBatchCreateEntry]
    ) -> AsyncIterator[tuple[int | None, BmpBatchItemResult | None, list[int] | None]]:
        # Serialize lookup + draft persistence within this mailbox. Callers persist
        # operation intent and own distributed task execution in Schedule Assistant.
        async with self._operation_lock:
            pending: list[BmpBatchCreateEntry] = []
            indexes: list[int] = []
            seen_operations: set[str] = set()
            for index, entry in enumerate(entries):
                if entry.operation_id in seen_operations:
                    yield (
                        index,
                        BmpBatchItemResult(
                            status="error", error="Duplicate operation_id in batch; reconcile existing operation"
                        ),
                        None,
                    )
                    continue
                if entry.operation_id:
                    seen_operations.add(entry.operation_id)
                    try:
                        existing = await asyncio.to_thread(
                            self._find_identity_items,
                            ReconcileBookingEntry(
                                operation_id=entry.operation_id,
                                room_id=entry.room.id,
                            ),
                        )
                        if existing:
                            item = existing[0]
                            if (
                                item.start != entry.start
                                or item.end != entry.end
                                or item.subject != self._auto_subject(entry.title)
                                or item.recurrence != entry.recurrence
                            ):
                                raise HTTPException(409, "Operation ID was already used for another booking")
                            booking = self.booking_from_calendar_item(item, room_id=entry.room.id)
                            if booking is None:
                                raise HTTPException(409, "Operation room does not match")
                            response, _, body = await asyncio.to_thread(
                                self._recover_room_response, item, entry.room.resource_email
                            )
                            booking.room_response = cast(BookingStatus, response or "Unknown")
                            booking.message_body = body
                            if item.meeting_request_was_sent is not True and response not in (
                                "Accept",
                                "Tentative",
                                "Decline",
                            ):
                                booking.room_response = "Unknown"
                                booking.message_body = (
                                    "Organizer item exists; invitation send is unverified. Do not resend."
                                )
                            entry.sent_booking = booking
                            yield (None, None, [index])
                            yield (index, BmpBatchItemResult(status="ok", booking=booking, message_body=body), None)
                            continue
                        if entry.operation_id in self._uncertain_operations:
                            raise HTTPException(409, "Previous create outcome is unknown; reconcile before retrying")
                    except Exception as exc:
                        yield (index, BmpBatchItemResult(status="error", error=str(exc)), None)
                        continue
                pending.append(entry)
                indexes.append(index)
            if not pending:
                return
            async for local_index, result, sent in self._create_new_chunk(pending):
                if sent is not None:
                    yield (None, None, [indexes[index] for index in sent])
                elif local_index is not None:
                    yield (indexes[local_index], result, None)

    async def _create_new_chunk(
        self, entries: list[BmpBatchCreateEntry]
    ) -> AsyncIterator[tuple[int | None, BmpBatchItemResult | None, list[int] | None]]:
        items = [
            self._build_calendar_item(
                room=entry.room,
                start=entry.start,
                end=entry.end,
                title=entry.title,
                participant_emails=entry.participant_emails,
                recurrence=entry.recurrence,
                categories=entry.categories,
                description=entry.description,
                operation_id=entry.operation_id,
            )
            for entry in entries
        ]

        def _bulk_create() -> list[exchangelib.items.BulkCreateResult | Exception]:
            # Persist operation marker before invitations. A restart or ambiguous send
            # finds this organizer item and must reconcile, not create a second one.
            return self.selected_calendar.bulk_create(
                items,
                send_meeting_invitations=exchangelib.items.SEND_TO_NONE,
            )

        t_create = tm.monotonic()
        self._uncertain_operations.update(entry.operation_id for entry in entries if entry.operation_id)
        try:
            create_results = await asyncio.to_thread(_bulk_create)
        except Exception as exc:
            for index, entry in enumerate(entries):
                booking = self.booking_from_calendar_item(items[index], room_id=entry.room.id)
                if booking is not None:
                    booking.outlook_booking_id = None
                    booking.source_item_id = None
                    booking.room_response = "Unknown"
                yield (
                    index,
                    BmpBatchItemResult(
                        status="error",
                        booking=booking,
                        error=f"Exchange send outcome unknown; reconcile operation before retrying: {exc}",
                    ),
                    None,
                )
            return
        logger.info(f"create_bookings_batch: bulk_create {len(entries)} items took {tm.monotonic() - t_create:.3f}s")

        sent_indexes: list[int] = []
        confirm_jobs: list[tuple[int, exchangelib.items.BulkCreateResult]] = []
        for index, (entry, create_result) in enumerate(zip(entries, create_results, strict=True)):
            if isinstance(create_result, Exception):
                logger.info(f"create_bookings_batch: confirm room={entry.room.id} failed at create: {create_result}")
                yield (
                    index,
                    BmpBatchItemResult(status="error", error=str(create_result)),
                    None,
                )
                continue
            items[index].id = create_result.id
            items[index].changekey = create_result.changekey
            entry.sent_booking = self.booking_from_calendar_item(items[index], room_id=entry.room.id)
            if entry.sent_booking is not None:
                entry.sent_booking.organizer_mailbox = self.account_email
                entry.sent_booking.room_response = "Unknown"
            sent_indexes.append(index)
            confirm_jobs.append((index, create_result))

        for index in sent_indexes:
            try:
                # A real UpdateItem with SendToAllAndSaveCopy sends invitations
                # for the durable draft while retaining its operation marker.
                await asyncio.to_thread(
                    items[index].save,
                    update_fields=["subject"],
                    send_meeting_invitations=exchangelib.items.SEND_TO_ALL_AND_SAVE_COPY,
                )
            except Exception as exc:
                logger.warning(
                    f"BMP invitation send outcome unknown for operation {entries[index].operation_id}: {exc}"
                )
                error_type = type(exc).__name__
                entries[
                    index
                ].send_error = f"Invitation send raised {error_type}; outcome unknown; reconcile before retrying"
                sent_booking = entries[index].sent_booking
                if sent_booking is not None:
                    sent_booking.message_body = "Invitation send outcome unknown; reconcile before retrying"
            yield (None, None, [index])

        async def _confirm_entry(
            entry: BmpBatchCreateEntry,
            create_result: exchangelib.items.BulkCreateResult,
        ) -> BmpBatchItemResult:
            if entry.send_error:
                return BmpBatchItemResult(status="error", booking=entry.sent_booking, error=entry.send_error)
            t_entry = tm.monotonic()
            item_id = str(create_result.id)
            try:
                booking, message_body = await self._confirm_booking(
                    room=entry.room,
                    item_id=item_id,
                    wait_before_poll=False,
                    timeout_s=settings.bmp_batch_confirm_timeout_s,
                )
                logger.info(
                    f"create_bookings_batch: confirm room={entry.room.id} item_id={item_id} ok "
                    f"({tm.monotonic() - t_entry:.3f}s)"
                )
                return BmpBatchItemResult(status="ok", booking=booking, message_body=message_body)
            except HTTPException as e:
                logger.info(
                    f"create_bookings_batch: confirm room={entry.room.id} item_id={item_id} "
                    f"http {e.status_code} ({tm.monotonic() - t_entry:.3f}s)"
                )
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
                return BmpBatchItemResult(
                    status="ok",
                    booking=entry.sent_booking,
                    error=error,
                    message_body=message_body,
                )
            except Exception as e:
                logger.exception(
                    f"create_bookings_batch: confirm room={entry.room.id} item_id={item_id} error "
                    f"({tm.monotonic() - t_entry:.3f}s)"
                )
                return BmpBatchItemResult(status="ok", booking=entry.sent_booking, error=str(e))

        async def _confirm_indexed(
            index: int,
            create_result: exchangelib.items.BulkCreateResult,
        ) -> tuple[int, BmpBatchItemResult]:
            return index, await _confirm_entry(entries[index], create_result)

        for finished in asyncio.as_completed(
            [_confirm_indexed(index, create_result) for index, create_result in confirm_jobs]
        ):
            index, result = await finished
            yield (index, result, None)


bmp_repository = BmpCalendarRepository(
    settings.exchange.ews_endpoint,
    settings.exchange.bmp.username,
    settings.exchange.bmp.password.get_secret_value(),
)
