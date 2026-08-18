import datetime as dtm
from zlib import crc32

import icalendar
from pydantic import BaseModel, field_validator

from src.schedule.utils import get_color


class CleaningEntry(BaseModel):
    name: str = "Cleaning"
    location: str
    dates: list[dtm.date]


class LinenChangeEntry(BaseModel):
    name: str = "Linen change"
    location: str
    rrule: dict[str, str]


class CleaningParserConfig(BaseModel):
    start_date: dtm.date
    cleaning_entries: list[CleaningEntry]
    linen_change_entries: list[LinenChangeEntry]


class CleaningParser:
    config: CleaningParserConfig

    def __init__(self, config: CleaningParserConfig):
        self.config = config

    def get_cleaning_events(self) -> list[CleaningEvent]:
        """
        Get cleaning events

        :return: cleaning events
        :rtype: list[CleaningEvent]
        """
        events = []

        for cleaning_entry in self.config.cleaning_entries:
            events.append(
                CleaningEvent(
                    summary=cleaning_entry.name,
                    location=cleaning_entry.location,
                    date=cleaning_entry.dates[0],
                    rdate=cleaning_entry.dates,
                )
            )

        return events

    def get_linen_change_schedule(self) -> list[LinenChangeEvent]:
        """
        Get linen change schedule

        :return: linen change schedule
        :rtype: list[LinenChangeEvent]
        """

        events = []

        for linen_change_entry in self.config.linen_change_entries:
            events.append(
                LinenChangeEvent(
                    summary=linen_change_entry.name,
                    location=linen_change_entry.location,
                    rrule=linen_change_entry.rrule,
                    date=self.config.start_date,
                )
            )

        return events


class CleaningEvent(BaseModel):
    summary: str
    location: str
    date: dtm.date
    rdate: list[dtm.date]

    @field_validator("rdate", mode="before")
    @classmethod
    def remove_repeat_dates(cls, v):
        return list(set(v))

    def get_uid(self) -> str:
        """
        Get unique id of the event
        """
        string_to_hash = str(("cleaning", self.summary, self.location, self.date.isoformat()))
        hash_ = crc32(string_to_hash.encode("utf-8"))

        return f"{abs(hash_):x}#cleaning@innohassle.ru"

    def get_vevent(self) -> icalendar.Event:
        """
        Get icalendar event

        :return: icalendar event
        :rtype: icalendar.Event
        """
        event = icalendar.Event()
        event.add("summary", self.summary)
        event.add("location", self.location)
        event.add("dtstart", icalendar.vDate(self.date))
        event.add("uid", self.get_uid())
        self.rdate = sorted(self.rdate)
        event.add("rdate", self.rdate, parameters={"value": "DATE"})
        color = get_color(self.location[0])
        event.add("color", color)
        return event


class LinenChangeEvent(BaseModel):
    summary: str
    date: dtm.date
    description: str = "Working hours:\n13:00-17:00"
    location: str
    rrule: dict

    def get_uid(self) -> str:
        """
        Get unique id of the event
        """
        string_to_hash = str(("linen", self.summary, self.location))
        hash_ = crc32(string_to_hash.encode("utf-8"))
        return f"{abs(hash_):x}#linen@innohassle.ru"

    def get_vevent(self) -> icalendar.Event:
        """
        Get icalendar event
        """
        event = icalendar.Event()
        event.add("summary", self.summary)
        event.add("description", self.description)
        event.add("location", self.location)
        from src.schedule.utils import nearest_weekday

        event.add("dtstart", icalendar.vDate(nearest_weekday(self.date, self.rrule["byday"])))

        rrule = icalendar.vRecur(freq=self.rrule["freq"], byday=self.rrule["byday"])
        event.add("rrule", rrule)
        event.add("uid", self.get_uid())
        color = get_color(self.location[0])
        event.add("color", color)

        return event
