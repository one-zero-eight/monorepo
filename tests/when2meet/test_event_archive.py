import datetime as dtm

import pytest

from src.when2meet.modules.events.archive import SLOT_DURATION, archive_state, calculate_archive_after
from src.when2meet.modules.events.schemas import MeetingTime


def test_archive_after_uses_selected_time_end() -> None:
    slots = [dtm.datetime(2026, 8, 20, 18, 0, tzinfo=dtm.UTC)]
    selected_time = MeetingTime(
        start="2026-08-25T14:00:00+05:00",
        end="2026-08-25T15:30:00+05:00",
    )

    archive_after = calculate_archive_after(slots, selected_time)

    assert archive_after == dtm.datetime(
        2026,
        8,
        25,
        15,
        30,
        tzinfo=dtm.timezone(dtm.timedelta(hours=5)),
    )


def test_archive_after_uses_end_of_latest_slot() -> None:
    slots = [
        dtm.datetime(2026, 8, 22, 15, 0, tzinfo=dtm.UTC),
        dtm.datetime(2026, 8, 20, 18, 0, tzinfo=dtm.UTC),
        dtm.datetime(2026, 8, 22, 17, 30, tzinfo=dtm.UTC),
    ]

    archive_after = calculate_archive_after(slots, selected_time=None)

    assert archive_after == dtm.datetime(2026, 8, 22, 17, 30, tzinfo=dtm.UTC) + SLOT_DURATION


def test_archive_after_requires_slots_without_selected_time() -> None:
    with pytest.raises(ValueError, match="without meeting slots"):
        calculate_archive_after([], selected_time=None)


def test_archive_state_is_active_before_deadline() -> None:
    archive_after = dtm.datetime(2026, 8, 25, 15, 30, tzinfo=dtm.UTC)

    assert archive_state(
        archive_after,
        manually_archived_at=None,
        now=archive_after - dtm.timedelta(seconds=1),
    ) == (False, None)


def test_archive_state_is_automatic_at_deadline() -> None:
    archive_after = dtm.datetime(2026, 8, 25, 15, 30, tzinfo=dtm.UTC)

    assert archive_state(archive_after, manually_archived_at=None, now=archive_after) == (True, archive_after)


def test_manual_archive_takes_priority_over_automatic_deadline() -> None:
    archive_after = dtm.datetime(2026, 8, 25, 15, 30, tzinfo=dtm.UTC)
    manually_archived_at = archive_after - dtm.timedelta(days=1)

    assert archive_state(
        archive_after,
        manually_archived_at=manually_archived_at,
        now=archive_after + dtm.timedelta(days=1),
    ) == (True, manually_archived_at)
