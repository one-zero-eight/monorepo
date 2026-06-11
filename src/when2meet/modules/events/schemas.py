import datetime as dtm

from src.common_pydantic import BaseSchema


class EventCreate(BaseSchema):
    name: str
    "Name of the event"
    description: str | None = None
    "Description of the event"
    slots: list[dtm.datetime]
    "All possible slots for the event"


class ParticipantUpdate(BaseSchema):
    name: str
    "Name of the participant"
    availability: list[dtm.datetime]
    "List of slots the participant is available for"
