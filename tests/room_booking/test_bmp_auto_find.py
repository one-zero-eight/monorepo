import datetime as dtm
from types import SimpleNamespace

from src.room_booking.modules.bmp.repository import auto_item_overlaps_window
from tests.room_booking.datetime_helpers import msk


def test_single_item_overlaps_window():
    item = SimpleNamespace(
        start=msk(2026, 9, 1, 10),
        end=msk(2026, 9, 1, 12),
        recurrence=None,
    )
    assert auto_item_overlaps_window(item, msk(2026, 8, 25, 0), msk(2026, 10, 26, 0))
    assert not auto_item_overlaps_window(item, msk(2026, 10, 1, 0), msk(2026, 10, 26, 0))


def test_weekly_master_overlaps_window_by_series_end_not_first_occurrence():
    item = SimpleNamespace(
        start=msk(2026, 8, 25, 10),
        end=msk(2026, 8, 25, 12),
        recurrence=SimpleNamespace(
            boundary=SimpleNamespace(start=dtm.date(2026, 8, 25), end=dtm.date(2026, 10, 26)),
        ),
    )
    assert auto_item_overlaps_window(item, msk(2026, 9, 1, 0), msk(2026, 9, 8, 0))
    assert not auto_item_overlaps_window(item, msk(2026, 11, 1, 0), msk(2026, 11, 30, 0))


def test_open_ended_series_overlaps_any_window_after_start():
    item = SimpleNamespace(
        start=msk(2026, 8, 25, 10),
        end=msk(2026, 8, 25, 12),
        recurrence=SimpleNamespace(boundary=SimpleNamespace(start=dtm.date(2026, 8, 25), end=None)),
    )
    assert auto_item_overlaps_window(item, msk(2026, 10, 1, 0), msk(2026, 10, 8, 0))
    assert not auto_item_overlaps_window(item, msk(2026, 8, 1, 0), msk(2026, 8, 10, 0))
