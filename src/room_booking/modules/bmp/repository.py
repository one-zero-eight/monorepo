"""BMP Specialist calendar — dedicated mailbox, default calendar, Auto-tagged events."""

# ruff: noqa: BLE001
import asyncio
import datetime as dtm
import time as tm
from collections.abc import AsyncIterator, Iterable
from typing import Any, Literal, Protocol, cast

import exchangelib
from exchangelib import Q
from exchangelib.recurrence import Recurrence
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from src.inh_accounts_sdk import UserSchema
from src.logging_ import logger
from src.room_booking.config import settings
from src.room_booking.config_schema import Room
from src.room_booking.modules.bookings.exchange_repository import ExchangeBookingRepository
from src.room_booking.modules.bookings.schemas import Booking
from src.room_booking.modules.bookings.tz_utils import to_msk

AUTO_SUBJECT_PREFIX = "Auto: "
AUTO_CATEGORY = "Auto"
BMP_CREATE_CHUNK_SIZE = 16

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
        **kwargs,
    ) -> exchangelib.CalendarItem:
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
        chain_category: str = AUTO_CATEGORY,
    ) -> list[exchangelib.CalendarItem]:
        return list(
            self.selected_calendar.filter(categories__contains=chain_category).only(
                "id", "changekey", "subject", "organizer", "categories"
            )
        )

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
        cancelled: list[str] = []
        failed: dict[str, str] = {}
        for item in items:
            item_id = str(item.id)
            try:
                await self.cancel_booking(item, email=self.account_email)
                cancelled.append(item_id)
            except Exception as e:
                failed[item_id] = str(e)
        result = CancelAllAutoBookingsResult(cancelled=cancelled, failed=failed)
        logger.info(f"Canceled {len(result.cancelled)}/{len(result.cancelled) + len(result.failed)} auto bookings")
        return result

    async def cancel_bookings_batch(
        self,
        outlook_booking_ids: list[str],
        *,
        email: str | None = None,
    ) -> CancelAllAutoBookingsResult:
        if not outlook_booking_ids:
            return CancelAllAutoBookingsResult(cancelled=[], failed={})

        cancelled: list[str] = []
        failed: dict[str, str] = {}

        for booking_id in outlook_booking_ids:
            if await self._recently.is_canceled(booking_id):
                cancelled.append(booking_id)
                continue
            item = await self.get_booking(booking_id)
            if item is None:
                failed[booking_id] = "Booking not found"
                continue
            try:
                await self.cancel_booking(item, email=email)
                cancelled.append(booking_id)
            except Exception as e:
                failed[booking_id] = str(e)

        result = CancelAllAutoBookingsResult(cancelled=cancelled, failed=failed)
        logger.info(f"Batch canceled {len(result.cancelled)}/{len(outlook_booking_ids)} auto bookings (email={email})")
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
            )
            for entry in entries
        ]

        def _bulk_create() -> list[exchangelib.items.BulkCreateResult | Exception]:
            return self.selected_calendar.bulk_create(
                items,
                send_meeting_invitations=exchangelib.items.SEND_TO_ALL_AND_SAVE_COPY,
            )

        t_create = tm.monotonic()
        create_results = await asyncio.to_thread(_bulk_create)
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
            sent_indexes.append(index)
            confirm_jobs.append((index, create_result))

        if sent_indexes:
            yield (None, None, sent_indexes)

        async def _confirm_entry(
            entry: BmpBatchCreateEntry,
            create_result: exchangelib.items.BulkCreateResult,
        ) -> BmpBatchItemResult:
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
                    status="error",
                    error=error,
                    message_body=message_body,
                )
            except Exception as e:
                logger.exception(
                    f"create_bookings_batch: confirm room={entry.room.id} item_id={item_id} error "
                    f"({tm.monotonic() - t_entry:.3f}s)"
                )
                return BmpBatchItemResult(status="error", error=str(e))

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
