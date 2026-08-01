import datetime as dtm

BOOKING_FETCH_MAX_DAYS = 62
MSK = dtm.timezone(dtm.timedelta(hours=3))


def resolve_booking_fetch_window(
    start_date: dtm.date,
    end_date: dtm.date,
    *,
    now: dtm.datetime | None = None,
) -> tuple[dtm.datetime, dtm.datetime] | None:
    """Build an Outlook-safe booking fetch window.

    Starts at the later of ``start_date`` and today (MSK), and spans at most
    ``BOOKING_FETCH_MAX_DAYS`` days (EWS FreeBusy limit), capped by ``end_date``.
    Returns ``None`` when the window is empty.
    """
    if now is None:
        now = dtm.datetime.now(MSK)
    else:
        now = now.astimezone(MSK)

    fetch_start = max(start_date, now.date())
    if fetch_start > end_date:
        return None

    start_dt = dtm.datetime.combine(fetch_start, dtm.time.min, tzinfo=MSK)
    end_dt = min(
        start_dt + dtm.timedelta(days=BOOKING_FETCH_MAX_DAYS),
        dtm.datetime.combine(end_date, dtm.time.max, tzinfo=MSK),
    )
    if start_dt >= end_dt:
        return None
    return start_dt, end_dt
