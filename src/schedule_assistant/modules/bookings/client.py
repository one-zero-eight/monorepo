import datetime as dtm
from collections.abc import AsyncGenerator
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urljoin

import httpx
from pydantic import Field

from src.clients.room_booking import (
    BmpBatchCancelRequest,
    BmpReconcileRequest,
    CancelExtraBookingRequest,
    ReconcileBookingEntry,
    RoomBookingClient,
    ScopedCancelBookingRequest,
)
from src.schedule_assistant.config import settings
from src.schedule_assistant.modules.bookings.schemas import BookingEvidence, BookingItemResultStatus
from src.schedule_assistant.schema_base import ScheduleAssistantSchema

HTTP_TIMEOUT_SECONDS = 300.0
# Read timeout is per-chunk of bytes. BMP sends `ping` while idle, but proxies
# may swallow those; keep this aligned with the booking task wall clock.
STREAM_TIMEOUT = httpx.Timeout(connect=30.0, read=3600.0, write=120.0, pool=30.0)


class BookingDTO(BookingEvidence):
    """Booking description"""

    event_id: str | None = None
    "ID of the event"
    title: str
    "Title of the booking"
    start_time: dtm.datetime = Field(validation_alias="start")
    "Start time of booking"
    end_time: dtm.datetime = Field(validation_alias="end")
    "End time of booking"
    categories: list[str] | None = None
    "Outlook categories on the calendar item"
    recurrence: str | None = None
    "EWS recurrence XML for recurring masters"
    outlook_booking_id: str | None = None
    "ID of outlook booking in service account calendar. Only set if we can manage the booking."
    outlook_entry_id: str | None = None
    "Hex Entry Id from Outlook free/busy. Set when we cannot manage the booking."
    busy_type: str | None = None
    source: Literal["organizer", "room", "free_busy"] = "organizer"
    source_item_id: str | None = None
    change_key: str | None = None
    attendees: list[dict[str, Any]] | None = None
    recurrence_complete: bool = Field(default_factory=lambda data: not bool(data.get("recurrence")))
    deleted_occurrences: list[str] = Field(default_factory=list)
    modified_occurrences: list[dict[str, Any]] = Field(default_factory=list)


class RoomDTO(ScheduleAssistantSchema):
    """Room description."""

    id: str
    "Room slug"
    title: str | None = None
    "Room title"
    short_name: str | None = None
    "Shorter version of room title"
    my_uni_id: int | None = None
    "ID of room on My University portal"
    capacity: int | None = None
    "Room capacity, amount of people"
    access_level: Literal["yellow", "red", "special"] | None = None
    "Access level to the room. Yellow = for students. Red = for employees. Special = special rules apply."
    restrict_daytime: bool = False
    "Prohibit to book during working hours. True = this room is available only at night 19:00-8:00, or full day on weekends."


class BmpStreamEventKind(StrEnum):
    STARTED = "started"
    SENT = "sent"
    ITEM = "item"
    DONE = "done"
    PING = "ping"


class BmpStreamEvent(BookingEvidence):
    event: BmpStreamEventKind
    total: int | None = None
    indexes: list[str] | None = None
    index: str | None = None
    status: BookingItemResultStatus | None = None
    title: str | None = None
    error: str | None = None
    booking: BookingEvidence | None = None
    items: list[BookingEvidence] = Field(default_factory=list)


class CancelAutoBookingsResult(ScheduleAssistantSchema):
    cancelled: list[str]
    failed: dict[str, str]


class BookingClient:
    def __init__(self, url: str, api_key: str) -> None:
        self.url = url if url.endswith("/") else f"{url}/"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._http_client: httpx.AsyncClient | None = None
        self._api_key = api_key

    @property
    def http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient()
        return self._http_client

    @property
    def api(self) -> RoomBookingClient:
        return RoomBookingClient(
            self.http_client,
            base_url=self.url,
            credentials={"Bearer": self._api_key},
            timeout=5.0,
        )

    async def aclose(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def get_room_bookings(
        self,
        room_id: str,
        start: dtm.datetime,
        end: dtm.datetime,
    ) -> list[BookingDTO]:
        bookings = await self.api.rooms_room_bookings_route(room_id, start, end)
        # Preserve domain defaults and enrichment rather than applying generated defaults.
        return [BookingDTO.model_validate(booking.model_dump(exclude_unset=True)) for booking in bookings]

    async def get_all_bookings(
        self,
        start: dtm.datetime,
        end: dtm.datetime,
    ) -> list[BookingDTO]:
        bookings = await self.api.bookings_bookings(
            start=start, end=end, include_red=True, timeout=HTTP_TIMEOUT_SECONDS
        )
        return [BookingDTO.model_validate(booking.model_dump(exclude_unset=True)) for booking in bookings]

    async def get_rooms(self) -> list[RoomDTO]:
        rooms = await self.api.rooms_rooms(include_red=True)
        return [RoomDTO.model_validate(room.model_dump(exclude_unset=True)) for room in rooms]

    async def get_auto_bookings(
        self,
        start: dtm.datetime,
        end: dtm.datetime,
    ) -> list[BookingDTO]:
        bookings = await self.api.bmp_specialist_list_auto_bookings(start=start, end=end, timeout=HTTP_TIMEOUT_SECONDS)
        return [BookingDTO.model_validate(booking.model_dump(exclude_unset=True)) for booking in bookings]

    async def stream_auto_bookings_batch(self, bookings: list[dict[str, Any]]) -> AsyncGenerator[BmpStreamEvent]:
        async with self.http_client.stream(
            "POST",
            urljoin(self.url, "bmp/auto-bookings/batch"),
            headers=self._headers,
            json={"bookings": bookings},
            timeout=STREAM_TIMEOUT,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                yield BmpStreamEvent.model_validate_json(line)

    async def reconcile_auto_bookings(self, entries: list[dict[str, Any]]) -> list[BookingEvidence]:
        evidence = await self.api.bmp_specialist_reconcile_auto_bookings(
            BmpReconcileRequest(entries=[ReconcileBookingEntry.model_validate(entry) for entry in entries]),
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        return [BookingEvidence.model_validate(entry.model_dump(exclude_unset=True)) for entry in evidence]

    async def cancel_booking_intent(self, payload: dict[str, Any]) -> BookingEvidence:
        evidence = await self.api.bmp_specialist_cancel_scoped_auto_booking(
            ScopedCancelBookingRequest.model_validate(payload), timeout=HTTP_TIMEOUT_SECONDS
        )
        return BookingEvidence.model_validate(evidence.model_dump(exclude_unset=True))

    async def cancel_auto_booking(self, outlook_booking_id: str) -> None:
        await self.api.bmp_specialist_delete_auto_booking(outlook_booking_id, timeout=HTTP_TIMEOUT_SECONDS)

    async def cancel_auto_bookings_batch(self, outlook_booking_ids: list[str]) -> CancelAutoBookingsResult:
        result = await self.api.bmp_specialist_batch_cancel_auto_bookings(
            BmpBatchCancelRequest(outlook_booking_ids=outlook_booking_ids), timeout=HTTP_TIMEOUT_SECONDS
        )
        return CancelAutoBookingsResult.model_validate(result.model_dump(exclude_unset=True))

    async def cancel_extra_booking(
        self,
        *,
        room_id: str,
        start: str,
        end: str,
        title: str,
        outlook_booking_id: str | None = None,
        outlook_entry_id: str | None = None,
    ) -> None:
        await self.api.bmp_specialist_cancel_extra_auto_booking(
            CancelExtraBookingRequest(
                room_id=room_id,
                start=dtm.datetime.fromisoformat(start),
                end=dtm.datetime.fromisoformat(end),
                title=title,
                outlook_booking_id=outlook_booking_id or None,
                outlook_entry_id=outlook_entry_id or None,
            ),
            timeout=HTTP_TIMEOUT_SECONDS,
        )


booking_client: BookingClient = BookingClient(
    url=settings.booking.api_url,
    api_key=settings.booking.api_key.get_secret_value(),
)
