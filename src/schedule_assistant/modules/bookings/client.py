import datetime as dtm
from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import quote, urljoin

import httpx
from pydantic import Field

from src.schedule_assistant.config import settings
from src.schedule_assistant.modules.bookings.schemas import BookingItemResultStatus
from src.schedule_assistant.schema_base import ScheduleAssistantSchema

HTTP_TIMEOUT_SECONDS = 300.0
STREAM_TIMEOUT_SECONDS = 600.0


class BookingDTO(ScheduleAssistantSchema):
    """Booking description"""

    room_id: str
    "ID of the room"
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


class BmpStreamEvent(ScheduleAssistantSchema):
    event: BmpStreamEventKind
    total: int | None = None
    indexes: list[str] | None = None
    index: str | None = None
    status: BookingItemResultStatus | None = None
    title: str | None = None
    error: str | None = None
    message_body: str | None = None


class CancelAutoBookingsResult(ScheduleAssistantSchema):
    cancelled: list[str]
    failed: dict[str, str]


class BookingClient:
    def __init__(self, url: str, api_key: str) -> None:
        self.url = url if url.endswith("/") else f"{url}/"
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def get_room_bookings(
        self,
        room_id: str,
        start: dtm.datetime,
        end: dtm.datetime,
    ) -> list[BookingDTO]:
        async with httpx.AsyncClient(headers=self._headers) as client:
            safe_room_id = quote(room_id, safe="")
            full_url = urljoin(self.url, f"room/{safe_room_id}/bookings")
            response = await client.get(
                full_url,
                params={"start": start.isoformat(), "end": end.isoformat()},
            )
            response.raise_for_status()
            data = response.json()
            return [BookingDTO.model_validate(entry) for entry in data]

    async def get_all_bookings(
        self,
        start: dtm.datetime,
        end: dtm.datetime,
    ) -> list[BookingDTO]:
        async with httpx.AsyncClient(headers=self._headers) as client:
            response = await client.get(
                urljoin(self.url, "bookings/"),
                params={"start": start.isoformat(), "end": end.isoformat(), "include_red": True},
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            return [BookingDTO.model_validate(entry) for entry in data]

    async def get_rooms(self) -> list[RoomDTO]:
        async with httpx.AsyncClient(headers=self._headers) as client:
            response = await client.get(urljoin(self.url, "rooms/"), params={"include_red": True})
            response.raise_for_status()
            return [RoomDTO.model_validate(entry) for entry in response.json()]

    async def get_auto_bookings(
        self,
        start: dtm.datetime,
        end: dtm.datetime,
    ) -> list[BookingDTO]:
        async with httpx.AsyncClient(headers=self._headers) as client:
            response = await client.get(
                urljoin(self.url, "bmp/auto-bookings/"),
                params={"start": start.isoformat(), "end": end.isoformat()},
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            return [BookingDTO.model_validate(entry) for entry in data]

    async def stream_auto_bookings_batch(self, bookings: list[dict[str, Any]]) -> AsyncIterator[BmpStreamEvent]:
        async with (
            httpx.AsyncClient(headers=self._headers) as client,
            client.stream(
                "POST",
                urljoin(self.url, "bmp/auto-bookings/batch"),
                json={"bookings": bookings},
                timeout=STREAM_TIMEOUT_SECONDS,
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                yield BmpStreamEvent.model_validate_json(line)

    async def cancel_auto_booking(self, outlook_booking_id: str) -> None:
        async with httpx.AsyncClient(headers=self._headers) as client:
            response = await client.delete(
                urljoin(self.url, f"bmp/auto-bookings/{quote(outlook_booking_id, safe='')}"),
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()

    async def cancel_auto_bookings_batch(self, outlook_booking_ids: list[str]) -> CancelAutoBookingsResult:
        async with httpx.AsyncClient(headers=self._headers) as client:
            response = await client.request(
                "DELETE",
                urljoin(self.url, "bmp/auto-bookings/batch"),
                json={"outlook_booking_ids": outlook_booking_ids},
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return CancelAutoBookingsResult.model_validate(response.json())

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
        body: dict[str, Any] = {
            "room_id": room_id,
            "start": start,
            "end": end,
            "title": title,
        }
        if outlook_booking_id:
            body["outlook_booking_id"] = outlook_booking_id
        if outlook_entry_id:
            body["outlook_entry_id"] = outlook_entry_id
        async with httpx.AsyncClient(headers=self._headers) as client:
            response = await client.post(
                urljoin(self.url, "bookings/cancel-extra"),
                json=body,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()


booking_client: BookingClient = BookingClient(
    url=settings.booking.api_url,
    api_key=settings.booking.api_key.get_secret_value(),
)
