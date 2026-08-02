import datetime as dtm
from enum import StrEnum


class Weekday(StrEnum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"

    @property
    def index(self) -> int:
        return list(Weekday).index(self)


WEEKDAYS = [day.value for day in Weekday]


def week_start_for_date(value: dtm.date, starting_day: Weekday = Weekday.MONDAY) -> dtm.date:
    return value - dtm.timedelta(days=(value.weekday() - starting_day.index) % 7)


def weekday_index(name: str) -> int:
    return WEEKDAYS.index(Weekday[name.upper().strip()].value)
