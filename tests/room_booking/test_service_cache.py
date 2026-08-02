import datetime as dtm

import pytest

from src.room_booking.modules.bookings.caching import CacheEntry, CacheForBookings
from src.room_booking.modules.bookings.schemas import Attendee, Booking


def _booking(room_id: str = "r1", start_offset: int = 0, end_offset: int = 3600) -> Booking:
    base = dtm.datetime(2025, 2, 14, 10, 0, 0, tzinfo=dtm.UTC)
    return Booking(
        room_id=room_id,
        title="Meeting",
        start=base + dtm.timedelta(seconds=start_offset),
        end=base + dtm.timedelta(seconds=end_offset),
        outlook_booking_id="oid-1",
        outlook_entry_id=None,
        attendees=[Attendee(email="a@b.com", status="Accept", assosiated_room_id=None)],
        related_to_me=None,
    )


def test_cache_entry_stores_bookings_start_end_timestamp():
    b = _booking()
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    ts = 1000.0  # monotonic timestamp
    entry = CacheEntry(bookings=[b], start=start, end=end, timestamp=ts)
    assert entry.bookings == [b]
    assert entry.start == start
    assert entry.end == end
    assert entry.timestamp == ts


def test_cache_accepts_ttl_as_int_seconds():
    cache = CacheForBookings(ttl=60)
    assert cache.ttl_sec == 60.0


def test_cache_accepts_ttl_as_timedelta():
    cache = CacheForBookings(ttl=dtm.timedelta(minutes=5))
    assert cache.ttl_sec == 300.0


@pytest.mark.anyio
async def test_update_cache_stores_copy():
    cache = CacheForBookings(ttl=60)
    b = _booking()
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    now = 1000.0

    await cache.update_cache("r1", [b], start, end, now=now)
    b.title = "Modified"
    entry = await cache.get_cached_entry("r1", start, end, now=now)
    assert entry is not None
    assert entry.bookings[0].title == "Meeting"


@pytest.mark.anyio
async def test_get_cached_entry_hit():
    cache = CacheForBookings(ttl=3600)
    b = _booking()
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    now = 1000.0

    await cache.update_cache("r1", [b], start, end, now=now)
    entry = await cache.get_cached_entry("r1", start, end, now=now)
    assert entry is not None
    assert len(entry.bookings) == 1
    assert entry.start == start and entry.end == end


@pytest.mark.anyio
async def test_get_cached_entry_request_within_range():
    cache = CacheForBookings(ttl=3600)
    b = _booking()
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    now = 1000.0
    req_start = dtm.datetime(2025, 2, 14, 10, 0, tzinfo=dtm.UTC)
    req_end = dtm.datetime(2025, 2, 14, 11, 0, tzinfo=dtm.UTC)

    await cache.update_cache("r1", [b], start, end, now=now)
    entry = await cache.get_cached_entry("r1", req_start, req_end, now=now)
    assert entry is not None
    assert entry.bookings[0].room_id == "r1"


@pytest.mark.anyio
async def test_get_cached_entry_miss_room_unknown():
    cache = CacheForBookings(ttl=3600)
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    now = 1000.0
    entry = await cache.get_cached_entry("r1", start, end, now=now)
    assert entry is None


@pytest.mark.anyio
async def test_get_cached_entry_miss_request_outside_range():
    cache = CacheForBookings(ttl=3600)
    b = _booking()
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    now = 1000.0
    req_start = dtm.datetime(2025, 2, 14, 13, 0, tzinfo=dtm.UTC)
    req_end = dtm.datetime(2025, 2, 14, 14, 0, tzinfo=dtm.UTC)

    await cache.update_cache("r1", [b], start, end, now=now)
    entry = await cache.get_cached_entry("r1", req_start, req_end, now=now)
    assert entry is None


@pytest.mark.anyio
async def test_get_cached_entry_miss_expired_removes_entry():
    cache = CacheForBookings(ttl=60)
    b = _booking()
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    now = 1000.0
    later = 1061.0  # 61s later, past 60s TTL

    await cache.update_cache("r1", [b], start, end, now=now)
    entry = await cache.get_cached_entry("r1", start, end, now=later)
    assert entry is None
    assert "r1" not in cache.cache


@pytest.mark.anyio
async def test_get_cached_entry_hit_at_ttl_boundary():
    cache = CacheForBookings(ttl=60)
    b = _booking()
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    now = 1000.0
    at_boundary = 1059.0  # 59s later, still within 60s TTL

    await cache.update_cache("r1", [b], start, end, now=now)
    entry = await cache.get_cached_entry("r1", start, end, now=at_boundary)
    assert entry is not None


@pytest.mark.anyio
async def test_update_cache_from_mapping():
    cache = CacheForBookings(ttl=60)
    b1 = _booking(room_id="r1")
    b2 = _booking(room_id="r2")
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    now = 1000.0

    await cache.update_cache_from_mapping({"r1": [b1], "r2": [b2]}, start, end, now=now)
    e1 = await cache.get_cached_entry("r1", start, end, now=now)
    e2 = await cache.get_cached_entry("r2", start, end, now=now)
    assert e1 is not None
    assert e2 is not None


@pytest.mark.anyio
async def test_get_cached_bookings_returns_hits_and_misses():
    cache = CacheForBookings(ttl=3600)
    b = _booking(room_id="r1")
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    now = 1000.0

    await cache.update_cache("r1", [b], start, end, now=now)
    room_x_cache, cache_misses = await cache.get_cached_bookings(["r1", "r2"], start, end, now=now)
    assert room_x_cache.keys() == {"r1"}
    assert len(room_x_cache["r1"]) == 1
    assert room_x_cache["r1"][0].room_id == "r1"
    assert cache_misses == {"r2"}


@pytest.mark.anyio
async def test_get_cached_bookings_all_miss():
    cache = CacheForBookings(ttl=3600)
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    now = 1000.0
    room_x_cache, cache_misses = await cache.get_cached_bookings(["r1", "r2"], start, end, now=now)
    assert room_x_cache == {}
    assert cache_misses == {"r1", "r2"}


@pytest.mark.anyio
async def test_get_cached_bookings_all_hit():
    cache = CacheForBookings(ttl=3600)
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    now = 1000.0

    await cache.update_cache("r1", [_booking(room_id="r1")], start, end, now=now)
    await cache.update_cache("r2", [_booking(room_id="r2")], start, end, now=now)
    room_x_cache, cache_misses = await cache.get_cached_bookings(["r1", "r2"], start, end, now=now)
    assert set(room_x_cache.keys()) == {"r1", "r2"}
    assert len(cache_misses) == 0


@pytest.mark.anyio
async def test_multiple_slots_query_finds_containing_slot():
    cache = CacheForBookings(ttl=3600, max_slots_per_room=5)
    now = 1000.0
    req_start = dtm.datetime(2025, 2, 14, 15, 0, tzinfo=dtm.UTC)
    req_end = dtm.datetime(2025, 2, 14, 16, 0, tzinfo=dtm.UTC)

    await cache.update_cache(
        "r1",
        [_booking(room_id="r1")],
        dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC),
        dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC),
        now=now,
    )
    await cache.update_cache(
        "r1",
        [_booking(room_id="r1", start_offset=3600, end_offset=7200)],
        dtm.datetime(2025, 2, 14, 14, 0, tzinfo=dtm.UTC),
        dtm.datetime(2025, 2, 14, 18, 0, tzinfo=dtm.UTC),
        now=now,
    )
    entry = await cache.get_cached_entry("r1", req_start, req_end, now=now)
    assert entry is not None
    assert entry.start.hour == 14 and entry.end.hour == 18
    assert len(entry.bookings) == 1


@pytest.mark.anyio
async def test_evict_oldest_when_over_max_slots():
    cache = CacheForBookings(ttl=86400, max_slots_per_room=2)  # long ttl so none expire
    base_start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    base_end = dtm.datetime(2025, 2, 14, 10, 0, tzinfo=dtm.UTC)

    for i in range(3):
        await cache.update_cache("r1", [_booking()], base_start, base_end, now=1000.0 + i)
    entry = await cache.get_cached_entry("r1", base_start, base_end, now=1000.0)
    assert len(cache.cache["r1"]) == 2
    assert entry is not None


@pytest.mark.anyio
async def test_expired_slot_skipped_fresh_slot_used():
    cache = CacheForBookings(ttl=60, max_slots_per_room=5)
    old_now = 1000.0
    start = dtm.datetime(2025, 2, 14, 9, 0, tzinfo=dtm.UTC)
    end = dtm.datetime(2025, 2, 14, 12, 0, tzinfo=dtm.UTC)
    new_now = 1070.0  # 70s later, first slot expired

    await cache.update_cache("r1", [_booking(room_id="r1")], start, end, now=old_now)
    await cache.update_cache("r1", [_booking(room_id="r1", start_offset=3600)], start, end, now=new_now)
    entry = await cache.get_cached_entry("r1", start, end, now=new_now)
    assert entry is not None
    assert len(cache.cache["r1"]) == 1
