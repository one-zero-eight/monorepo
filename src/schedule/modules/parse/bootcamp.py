import datetime as dtm
import re
from collections.abc import Generator
from zlib import crc32

import icalendar
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schedule.modules.parse.utils import get_color


class Entry(BaseModel):
    subject: str | None = None
    subject_ru: str | None = None
    instructor: str | None = None
    location: str | None = None
    location_ru: str | None = None
    when: list[str] = Field(examples=[["1 10:00-12:00", "2-6 10:00-12:00"]])
    buddy: bool = False

    @field_validator("when", mode="before")
    @classmethod
    def string_to_list(cls, v):
        if isinstance(v, str):
            return [v]
        return v


class AcademicGroup(BaseModel):
    name: str
    ru: bool = False
    english: Entry | None = None
    labs: Entry | None = None

    math: Entry | None = None
    programming: Entry | None = None
    physics: Entry | None = None


class BuddyGroup(BaseModel):
    number: str
    name: str
    tg: str
    location: str


class BootcampParserConfig(BaseModel):
    when: str = Field(examples=["2024.08"])
    general_events: list[Entry]
    academic_groups: list[AcademicGroup]
    buddy_groups: list[BuddyGroup]


class BootcampEvent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    summary: str
    dtstart: dtm.datetime
    dtend: dtm.datetime
    rrule: icalendar.vRecur | None
    description: str | None
    location: str | None
    buddy: bool = False
    sequence: int = 0

    def get_uid(self) -> str:
        """
        Get unique id of the event
        """
        if self.buddy:
            string_to_hash = str(("bootcamp", "buddy", self.dtstart))
        else:
            string_to_hash = str(("bootcamp", self.summary, self.location, self.dtstart))
        hash_ = crc32(string_to_hash.encode("utf-8"))
        return f"{abs(hash_):x}#bootcamp@innohassle.ru"

    def get_color_category(self) -> str:
        """
        Get consistent color category for similar event types
        """
        summary = self.summary.lower()

        # Meals
        if any(meal in summary for meal in ["breakfast", "завтрак", "lunch", "обед", "dinner", "ужин"]):
            return "gray"

        # Academic subjects
        if any(
            subj in summary
            for subj in [
                "programming",
                "программирование",
                "physics",
                "физика",
                "math",
                "математический анализ",
                "english",
                "английский",
                "labs",
                "лабораторные",
                "introduction to computer science",
            ]
        ):
            return "darkcyan"

        # Special events
        if any(event in summary for event in ["meeting with buddy", "встреча с бадди"]):
            return "chocolate"

        if any(event in summary for event in ["workshop", "воркшоп"]):
            return "seagreen"

        if any(event in summary for event in ["лекция про университет", "iu lecture"]):
            return "indigo"

        return get_color(summary)

    def get_vevent(self) -> icalendar.Event:
        """
        Get icalendar event
        """
        event = icalendar.Event()
        event.add("summary", self.summary)
        if self.description:
            event.add("description", self.description)
        if self.location:
            event.add("location", self.location)
        event.add("dtstart", icalendar.vDatetime(self.dtstart))
        event.add("dtend", icalendar.vDatetime(self.dtend))
        if self.rrule:
            event.add("rrule", self.rrule)

        event.add("uid", self.get_uid())
        event.add("sequence", self.sequence)

        color = self.get_color_category()
        event.add("color", color)

        return event


class BootcampParser:
    config: BootcampParserConfig
    bootcamp_date: dtm.datetime

    def __init__(self, config: BootcampParserConfig):
        self.config = config
        self.bootcamp_date = dtm.datetime.strptime(self.config.when, "%Y.%m").replace(tzinfo=dtm.UTC)

    def parse_general_events(self, ru: bool = False) -> list[BootcampEvent]:
        events = []

        for entry in self.config.general_events:
            if ru and (entry.subject_ru is None and entry.location_ru is None):
                continue

            for when in entry.when:
                dtstart, dtend, rrule = self.when_str_to_datetimes(when)
                event = BootcampEvent(
                    summary=(entry.subject_ru or entry.subject or "") if ru else (entry.subject or ""),
                    dtstart=dtstart,
                    dtend=dtend,
                    rrule=rrule,
                    description=entry.instructor,
                    location=(entry.location_ru or entry.location) if ru else entry.location,
                    buddy=entry.buddy,
                )
                events.append(event)
        return events

    def when_str_to_datetimes(self, when: str) -> tuple[dtm.datetime, dtm.datetime, icalendar.vRecur | None]:
        day, period = when.split(" ")
        (start, end) = period.split("-")
        (start_hour, start_minute) = map(int, start.split(":"))
        (end_hour, end_minute) = map(int, end.split(":"))
        if "-" in day:
            start_day, end_day = map(int, day.split("-"))
            start_day = self.bootcamp_date.replace(day=start_day)
            end_day = self.bootcamp_date.replace(day=end_day, hour=end_hour, minute=end_minute)
            rrule = icalendar.vRecur({"FREQ": "DAILY", "INTERVAL": 1, "UNTIL": end_day})
        else:
            start_day = self.bootcamp_date.replace(day=int(day))
            rrule = None

        dtstart = start_day.replace(hour=start_hour, minute=start_minute)
        dtend = start_day.replace(hour=end_hour, minute=end_minute)
        return dtstart, dtend, rrule

    def parse_academic_group(
        self, academic_group: AcademicGroup, general_events: list[BootcampEvent], ru_general_events: list[BootcampEvent]
    ) -> list[BootcampEvent]:
        events = []

        if academic_group.ru:
            events.extend(ru_general_events)
        else:
            events.extend(general_events)

        ru_subjects = {
            "programming": "Программирование",
            "physics": "Физика",
            "math": "Математический анализ",
        }

        subjects = {
            "english": "English Practice",
            "labs": "Labs with TA",
        }

        for key, entry in [
            ("english", academic_group.english),
            ("labs", academic_group.labs),
            ("programming", academic_group.programming),
            ("math", academic_group.math),
            ("physics", academic_group.physics),
        ]:
            if entry is None:
                continue

            if academic_group.ru:
                subject = entry.subject_ru or ru_subjects[key]
                location = entry.location_ru or entry.location
            else:
                subject = entry.subject or subjects[key]
                location = entry.location

            for when in entry.when:
                dtstart, dtend, rrule = self.when_str_to_datetimes(when)
                event = BootcampEvent(
                    summary=subject,
                    dtstart=dtstart,
                    dtend=dtend,
                    rrule=rrule,
                    description=entry.instructor,
                    location=location,
                )
                events.append(event)

        return events

    def parse_buddy_group(self, buddy_group: BuddyGroup) -> list[BootcampEvent]:
        events = []

        for entry in self.config.general_events:
            # if buddy name is cyrillic, then it's a ru buddy group
            is_ru = re.match(r"[\u0400-\u04FF]", buddy_group.name)

            if is_ru:
                subject = entry.subject_ru or entry.subject
                location = entry.location_ru or entry.location
            else:
                subject = entry.subject
                location = entry.location

            if entry.buddy:
                for when in entry.when:
                    dtstart, dtend, rrule = self.when_str_to_datetimes(when)
                    event = BootcampEvent(
                        summary=f"{subject} {buddy_group.name}",
                        dtstart=dtstart,
                        dtend=dtend,
                        rrule=rrule,
                        location=location or buddy_group.location,
                        description=f"{buddy_group.name} {buddy_group.tg}",
                        buddy=True,
                        sequence=1,
                    )
                    events.append(event)

        return events

    def parse(self) -> Generator[tuple[AcademicGroup | BuddyGroup, list[BootcampEvent]]]:
        general_events = self.parse_general_events()
        ru_general_events = self.parse_general_events(ru=True)

        for academic_group in self.config.academic_groups:
            events = self.parse_academic_group(academic_group, general_events, ru_general_events)
            yield academic_group, events

        for buddy_group in self.config.buddy_groups:
            events = self.parse_buddy_group(buddy_group)
            yield buddy_group, events
