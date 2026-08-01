import datetime as dtm

import pytest

from src.schedule_assistant.modules.issues.booking_window import (
    BOOKING_FETCH_MAX_DAYS,
    MSK,
    resolve_booking_fetch_window,
)


def test_window_starts_at_semester_start_before_term() -> None:
    window = resolve_booking_fetch_window(
        dtm.date(2026, 9, 1),
        dtm.date(2026, 12, 31),
        now=dtm.datetime(2026, 8, 15, 12, 0, tzinfo=MSK),
    )
    assert window is not None
    start, end = window
    assert start == dtm.datetime(2026, 9, 1, 0, 0, tzinfo=MSK)
    assert end == dtm.datetime(2026, 9, 1, 0, 0, tzinfo=MSK) + dtm.timedelta(days=BOOKING_FETCH_MAX_DAYS)
    assert end - start == dtm.timedelta(days=BOOKING_FETCH_MAX_DAYS)


def test_window_starts_today_during_term() -> None:
    window = resolve_booking_fetch_window(
        dtm.date(2026, 9, 1),
        dtm.date(2026, 12, 31),
        now=dtm.datetime(2026, 10, 10, 9, 30, tzinfo=MSK),
    )
    assert window is not None
    start, end = window
    assert start == dtm.datetime(2026, 10, 10, 0, 0, tzinfo=MSK)
    assert end == start + dtm.timedelta(days=BOOKING_FETCH_MAX_DAYS)


def test_window_capped_by_semester_end() -> None:
    window = resolve_booking_fetch_window(
        dtm.date(2026, 6, 1),
        dtm.date(2026, 6, 20),
        now=dtm.datetime(2026, 6, 10, 0, 0, tzinfo=MSK),
    )
    assert window is not None
    start, end = window
    assert start == dtm.datetime(2026, 6, 10, 0, 0, tzinfo=MSK)
    assert end == dtm.datetime(2026, 6, 20, 23, 59, 59, 999999, tzinfo=MSK)
    assert end - start < dtm.timedelta(days=BOOKING_FETCH_MAX_DAYS)


def test_window_empty_after_semester() -> None:
    assert (
        resolve_booking_fetch_window(
            dtm.date(2026, 6, 1),
            dtm.date(2026, 8, 2),
            now=dtm.datetime(2026, 8, 3, 0, 0, tzinfo=MSK),
        )
        is None
    )


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (dtm.date(2026, 6, 1), dtm.date(2026, 12, 31)),
        (dtm.date(2026, 9, 1), dtm.date(2027, 1, 31)),
    ],
)
def test_window_never_exceeds_ews_limit(start: dtm.date, end: dtm.date) -> None:
    window = resolve_booking_fetch_window(
        start,
        end,
        now=dtm.datetime(2026, 9, 15, 12, 0, tzinfo=MSK),
    )
    assert window is not None
    fetch_start, fetch_end = window
    assert fetch_end - fetch_start <= dtm.timedelta(days=BOOKING_FETCH_MAX_DAYS)
