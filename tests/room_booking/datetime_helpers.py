import datetime as dtm

from src.room_booking.modules.bookings.tz_utils import msk_timezone


def msk(year: int, month: int, day: int, hour: int, minute: int = 0) -> dtm.datetime:
    return dtm.datetime(year, month, day, hour, minute, tzinfo=msk_timezone)


def dt_params(**kwargs: dtm.datetime | str | list[str]) -> dict[str, str | list[str]]:
    encoded: dict[str, str | list[str]] = {}
    for key, value in kwargs.items():
        if isinstance(value, dtm.datetime):
            encoded[key] = value.isoformat()
        else:
            encoded[key] = value
    return encoded
