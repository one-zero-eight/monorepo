import datetime as dtm

import pytest

from src.room_booking.modules.bookings.recently import RecentBookings
from src.room_booking.modules.bookings.schemas import Attendee, Booking


def _booking(
    room_id: str = "r1",
    start_offset: int = 0,
    end_offset: int = 3600,
    outlook_id: str | None = "oid-1",
    title: str = "Meeting",
) -> Booking:
    base = dtm.datetime(2025, 2, 14, 10, 0, 0, tzinfo=dtm.UTC)
    return Booking(
        room_id=room_id,
        title=title,
        start=base + dtm.timedelta(seconds=start_offset),
        end=base + dtm.timedelta(seconds=end_offset),
        outlook_booking_id=outlook_id,
        outlook_entry_id=None,
        attendees=[Attendee(email="a@b.com", status="Accept", assosiated_room_id=None)],
        related_to_me=None,
    )


def test_recently_accepts_ttl_as_int():
    rb = RecentBookings(ttl_sec=60)
    assert rb.ttl_sec == 60.0


def test_recently_accepts_ttl_as_float():
    rb = RecentBookings(ttl_sec=300.5)
    assert rb.ttl_sec == 300.5


@pytest.mark.anyio
async def test_mark_and_is_canceled_within_ttl():
    rb = RecentBookings(ttl_sec=60)
    now = 1000.0
    await rb.mark_canceled("id1", now=now)
    assert await rb.is_canceled("id1", now=now) is True
    assert await rb.is_canceled("id1", now=now + 30) is True
    assert await rb.is_canceled("id2", now=now) is False


@pytest.mark.anyio
async def test_canceled_expires_after_ttl():
    rb = RecentBookings(ttl_sec=60)
    now = 1000.0
    await rb.mark_canceled("id1", now=now)
    assert await rb.is_canceled("id1", now=now + 60) is False
    assert await rb.get_canceled(now=now + 60) == set()


@pytest.mark.anyio
async def test_get_canceled_returns_ids():
    rb = RecentBookings(ttl_sec=60)
    now = 1000.0
    await rb.mark_canceled("a", now=now)
    await rb.mark_canceled("b", now=now)
    assert await rb.get_canceled(now=now) == {"a", "b"}


@pytest.mark.anyio
async def test_mark_and_is_created_within_ttl():
    rb = RecentBookings(ttl_sec=60)
    now = 1000.0
    b = _booking(outlook_id="ex-1")
    await rb.mark_created("ex-1", b, now=now)
    assert await rb.is_created("ex-1", now=now) is True
    assert await rb.is_created("ex-1", now=now + 30) is True
    assert await rb.is_created("ex-2", now=now) is False


@pytest.mark.anyio
async def test_created_expires_after_ttl():
    rb = RecentBookings(ttl_sec=60)
    now = 1000.0
    b = _booking(outlook_id="ex-1")
    await rb.mark_created("ex-1", b, now=now)
    assert await rb.is_created("ex-1", now=now + 60) is False
    assert await rb.get_created(now=now + 60) == {}


@pytest.mark.anyio
async def test_get_created_returns_bookings():
    rb = RecentBookings(ttl_sec=60)
    now = 1000.0
    b1 = _booking(room_id="r1", outlook_id="ex-1")
    b2 = _booking(room_id="r2", outlook_id="ex-2")
    await rb.mark_created("ex-1", b1, now=now)
    await rb.mark_created("ex-2", b2, now=now)
    got = await rb.get_created(now=now)
    assert set(got.keys()) == {"ex-1", "ex-2"}
    assert got["ex-1"].room_id == "r1"
    assert got["ex-2"].room_id == "r2"


@pytest.mark.anyio
async def test_mark_and_is_updated_within_ttl():
    rb = RecentBookings(ttl_sec=60)
    now = 1000.0
    b = _booking(title="Updated", outlook_id="ex-1")
    await rb.mark_updated("ex-1", b, now=now)
    assert await rb.is_updated("ex-1", now=now) is True
    assert await rb.is_updated("ex-1", now=now + 30) is True
    assert await rb.is_updated("ex-2", now=now) is False


@pytest.mark.anyio
async def test_updated_expires_after_ttl():
    rb = RecentBookings(ttl_sec=60)
    now = 1000.0
    b = _booking(outlook_id="ex-1")
    await rb.mark_updated("ex-1", b, now=now)
    assert await rb.is_updated("ex-1", now=now + 60) is False
    assert await rb.get_updated_with_ts(now=now + 60) == {}


@pytest.mark.anyio
async def test_get_updated_returns_bookings():
    rb = RecentBookings(ttl_sec=60)
    now = 1000.0
    b = _booking(title="Updated", outlook_id="ex-1")
    await rb.mark_updated("ex-1", b, now=now)
    got = await rb.get_updated_with_ts(now=now)
    assert got == {"ex-1": (now, b)}
    assert got["ex-1"][1].title == "Updated"


@pytest.mark.anyio
async def test_canceled_created_updated_independent():
    rb = RecentBookings(ttl_sec=60)
    now = 1000.0
    bc = _booking(room_id="r1", outlook_id="c1")
    bu = _booking(room_id="r2", title="Updated", outlook_id="u1")
    await rb.mark_canceled("canceled-id", now=now)
    await rb.mark_created("c1", bc, now=now)
    await rb.mark_updated("u1", bu, now=now)

    assert await rb.get_canceled(now=now) == {"canceled-id"}
    assert list((await rb.get_created(now=now)).keys()) == ["c1"]
    assert list((await rb.get_updated_with_ts(now=now)).keys()) == ["u1"]


@pytest.mark.anyio
async def test_prune_removes_expired():
    rb = RecentBookings(ttl_sec=60)
    await rb.mark_canceled("old", now=1000.0)
    await rb.mark_created("old-b", _booking(outlook_id="old-b"), now=1000.0)
    await rb.mark_updated("old-u", _booking(outlook_id="old-u"), now=1000.0)

    await rb.mark_canceled("new", now=1061.0)
    await rb.mark_created("new-b", _booking(outlook_id="new-b"), now=1061.0)
    await rb.mark_updated("new-u", _booking(outlook_id="new-u"), now=1061.0)

    assert await rb.get_canceled(now=1061.0) == {"new"}
    assert set((await rb.get_created(now=1061.0)).keys()) == {"new-b"}
    assert set((await rb.get_updated_with_ts(now=1061.0)).keys()) == {"new-u"}
