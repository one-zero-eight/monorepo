import asyncio
import time as tm

from src.room_booking.modules.bookings.schemas import Booking


class RecentBookings:
    """TTL-backed cache for recently canceled (id -> timestamp), created and updated (id -> (timestamp, Booking))."""

    ttl_sec: float
    _canceled: dict[str, float]
    _created: dict[str, tuple[float, Booking]]
    _updated: dict[str, tuple[float, Booking]]
    _lock: asyncio.Lock

    def __init__(self, ttl_sec: float):
        self.ttl_sec = float(ttl_sec)
        self._canceled = {}
        self._created = {}
        self._updated = {}
        self._lock = asyncio.Lock()

    def _prune(self, now: float) -> None:
        self._canceled = {k: ts for k, ts in self._canceled.items() if now - ts < self.ttl_sec}
        self._created = {k: (ts, b) for k, (ts, b) in self._created.items() if now - ts < self.ttl_sec}
        self._updated = {k: (ts, b) for k, (ts, b) in self._updated.items() if now - ts < self.ttl_sec}

    async def mark_canceled(self, item_id: str, now: float | None = None) -> None:
        now = tm.monotonic() if now is None else now
        async with self._lock:
            self._prune(now)
            self._canceled[item_id] = now

    async def is_canceled(self, item_id: str, now: float | None = None) -> bool:
        now = tm.monotonic() if now is None else now
        async with self._lock:
            self._prune(now)
            ts = self._canceled.get(item_id)
            return ts is not None and (now - ts) < self.ttl_sec

    async def get_canceled(self, now: float | None = None) -> set[str]:
        now = tm.monotonic() if now is None else now
        async with self._lock:
            self._prune(now)
            return set(self._canceled.keys())

    async def mark_created(self, item_id: str, booking: Booking, now: float | None = None) -> None:
        now = tm.monotonic() if now is None else now
        async with self._lock:
            self._prune(now)
            self._created[item_id] = (now, booking)

    async def is_created(self, item_id: str, now: float | None = None) -> bool:
        now = tm.monotonic() if now is None else now
        async with self._lock:
            self._prune(now)
            entry = self._created.get(item_id)
            return entry is not None and (now - entry[0]) < self.ttl_sec

    async def get_created(self, now: float | None = None) -> dict[str, Booking]:
        now = tm.monotonic() if now is None else now
        async with self._lock:
            self._prune(now)
            return {k: b for k, (_, b) in self._created.items()}

    async def mark_updated(self, item_id: str, booking: Booking, now: float | None = None) -> None:
        now = tm.monotonic() if now is None else now
        async with self._lock:
            self._prune(now)
            self._updated[item_id] = (now, booking)

    async def is_updated(self, item_id: str, now: float | None = None) -> bool:
        now = tm.monotonic() if now is None else now
        async with self._lock:
            self._prune(now)
            entry = self._updated.get(item_id)
            return entry is not None and (now - entry[0]) < self.ttl_sec

    async def get_updated_with_ts(self, now: float | None = None) -> dict[str, tuple[float, Booking]]:
        now = tm.monotonic() if now is None else now
        async with self._lock:
            self._prune(now)
            return self._updated.copy()
