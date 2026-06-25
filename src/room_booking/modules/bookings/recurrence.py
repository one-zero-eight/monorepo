import datetime as dtm
from enum import StrEnum
from typing import Literal

import lxml.etree as etree  # ty: ignore[unresolved-import]
from exchangelib import Version
from exchangelib.fields import (
    FRIDAY,
    MONDAY,
    SATURDAY,
    SUNDAY,
    THURSDAY,
    TUESDAY,
    WEDNESDAY,
)
from exchangelib.recurrence import EndDatePattern, Recurrence, WeeklyPattern
from pydantic import BaseModel, Field, model_validator


class Weekday(StrEnum):
    monday = "monday"
    tuesday = "tuesday"
    wednesday = "wednesday"
    thursday = "thursday"
    friday = "friday"
    saturday = "saturday"
    sunday = "sunday"


_EXCHANGELIB_WEEKDAY = {
    Weekday.monday: MONDAY,
    Weekday.tuesday: TUESDAY,
    Weekday.wednesday: WEDNESDAY,
    Weekday.thursday: THURSDAY,
    Weekday.friday: FRIDAY,
    Weekday.saturday: SATURDAY,
    Weekday.sunday: SUNDAY,
}


class WeeklyUntilPattern(BaseModel):
    kind: Literal["weekly_until"] = "weekly_until"

    weekday: Weekday
    start_date: dtm.date
    until_date: dtm.date

    interval: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_dates(self) -> WeeklyUntilPattern:
        if self.until_date < self.start_date:
            raise ValueError("until_date must be greater than or equal to start_date")
        return self

    def to_exchangelib_recurrence(self) -> Recurrence:
        # EWS: WeeklyRecurrence + EndDateRecurrence
        # https://learn.microsoft.com/en-us/exchange/client-developer/web-service-reference/recurrence-recurrencetype
        return Recurrence(
            pattern=WeeklyPattern(
                interval=self.interval,
                weekdays=[_EXCHANGELIB_WEEKDAY[self.weekday]],
            ),
            boundary=EndDatePattern(start=self.start_date, end=self.until_date),
        )


type RecurrencePattern = WeeklyUntilPattern


def recurrence_to_xml(recurrence: Recurrence | None, *, version: Version) -> str | None:
    if recurrence is None:
        return None
    elem = recurrence.to_xml(version=version)
    return etree.tostring(elem, pretty_print=False, encoding="unicode")
