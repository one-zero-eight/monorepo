import datetime as dtm

from .schemas import MeetingTime

SLOT_DURATION = dtm.timedelta(minutes=30)


def calculate_archive_after(
    slots: list[dtm.datetime],
    selected_time: MeetingTime | None,
) -> dtm.datetime:
    if selected_time is not None:
        return selected_time.end_datetime
    if not slots:
        raise ValueError("Cannot calculate archive deadline without meeting slots")
    return max(slots) + SLOT_DURATION


def archive_state(
    archive_after: dtm.datetime,
    manually_archived_at: dtm.datetime | None,
    now: dtm.datetime,
) -> tuple[bool, dtm.datetime | None]:
    if manually_archived_at is not None:
        return True, manually_archived_at
    if archive_after <= now:
        return True, archive_after
    return False, None
