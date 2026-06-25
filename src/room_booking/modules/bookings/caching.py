import asyncio
import datetime as dtm
import time as tm
from collections.abc import Iterable
from dataclasses import dataclass

from src.room_booking.modules.bookings.schemas import Booking


@dataclass
class CacheSlot:
    bookings: list[Booking]
    start: dtm.datetime
    end: dtm.datetime
    timestamp: float  # time.monotonic()


# Alias for backward compatibility; get_cached_entry returns a slot-shaped value.
CacheEntry = CacheSlot


def _ttl_to_seconds(ttl: dtm.timedelta | int) -> float:
    if isinstance(ttl, int):
        return float(ttl)
    return ttl.total_seconds()


class CacheForBookings:
    ttl_sec: float
    max_slots_per_room: int
    cache: dict[str, list[CacheSlot]]
    _lock: asyncio.Lock

    def __init__(self, ttl: dtm.timedelta | int, max_slots_per_room: int = 10):
        self.ttl_sec = _ttl_to_seconds(ttl)
        self.max_slots_per_room = max_slots_per_room
        self.cache = {}
        self._lock = asyncio.Lock()

    def _prune_expired(self, room_id: str, now: float) -> None:
        slots = self.cache.get(room_id)
        if not slots:
            return
        valid = [s for s in slots if s.timestamp + self.ttl_sec > now]
        if not valid:
            self.cache.pop(room_id, None)
        else:
            self.cache[room_id] = valid

    def _evict_oldest(self, room_id: str) -> None:
        slots = self.cache.get(room_id, [])
        if len(slots) <= self.max_slots_per_room:
            return
        slots.sort(key=lambda s: s.timestamp)
        self.cache[room_id] = slots[-self.max_slots_per_room :]

    def _update_cache_impl(
        self,
        room_id: str,
        bookings: list[Booking],
        start: dtm.datetime,
        end: dtm.datetime,
        now: float,
    ) -> None:
        slot = CacheSlot(
            bookings=[b.model_copy() for b in bookings],
            start=start,
            end=end,
            timestamp=now,
        )
        if room_id not in self.cache:
            self.cache[room_id] = []
        self.cache[room_id].append(slot)
        self._prune_expired(room_id, now)
        self._evict_oldest(room_id)

    def _get_cached_entry_impl(
        self,
        room_id: str,
        start: dtm.datetime,
        end: dtm.datetime,
        now: float,
    ) -> CacheSlot | None:
        slots = self.cache.get(room_id)
        if not slots:
            return None
        not_outdated = [s for s in slots if s.timestamp + self.ttl_sec > now]
        if not not_outdated:
            self.cache.pop(room_id, None)
            return None
        for slot in not_outdated:
            if slot.start <= start and slot.end >= end:
                return CacheSlot(
                    bookings=[b.model_copy() for b in slot.bookings],
                    start=slot.start,
                    end=slot.end,
                    timestamp=slot.timestamp,
                )
        return None

    async def update_cache(
        self,
        room_id: str,
        bookings: list[Booking],
        start: dtm.datetime,
        end: dtm.datetime,
        now: float | None = None,
    ) -> None:
        now = now if now is not None else tm.monotonic()
        async with self._lock:
            self._update_cache_impl(room_id, bookings, start, end, now)

    async def update_cache_from_mapping(
        self,
        room_id_x_bookings: dict[str, list[Booking]],
        start: dtm.datetime,
        end: dtm.datetime,
        now: float | None = None,
    ) -> None:
        now = now if now is not None else tm.monotonic()
        async with self._lock:
            for room_id, bookings in room_id_x_bookings.items():
                self._update_cache_impl(room_id, bookings, start, end, now)

    async def get_cached_entry(
        self,
        room_id: str,
        start: dtm.datetime,
        end: dtm.datetime,
        now: float | None = None,
    ) -> CacheSlot | None:
        now = now if now is not None else tm.monotonic()
        async with self._lock:
            return self._get_cached_entry_impl(room_id, start, end, now)

    async def get_cached_bookings(
        self,
        room_ids: Iterable[str],
        start: dtm.datetime,
        end: dtm.datetime,
        now: float | None = None,
    ) -> tuple[dict[str, list[Booking]], set[str]]:
        now = now if now is not None else tm.monotonic()
        room_x_cache: dict[str, list[Booking]] = {}
        cache_misses: set[str] = set()
        async with self._lock:
            for room_id in room_ids:
                entry = self._get_cached_entry_impl(room_id, start, end, now)
                if entry is None:
                    cache_misses.add(room_id)
                else:
                    room_x_cache[room_id] = entry.bookings
        return room_x_cache, cache_misses
