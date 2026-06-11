__all__ = ["Event", "Participant", "document_models"]
import datetime as dtm

from pydantic import Field

from src.common_beanie import BeanieDocument
from src.common_pydantic import BaseSchema


class Participant(BaseSchema):
    name: str
    "Name of the participant"
    availability: list[dtm.datetime]
    "List of slots the participant is available for"


class Event(BeanieDocument):
    name: str
    "Name of the event"
    description: str | None = None
    "Description of the event"
    slots: list[dtm.datetime]
    "All possible slots for the event"
    participants: list[Participant] = Field(default_factory=list)
    "List of participants and their availability"
    created_at: dtm.datetime = Field(default_factory=lambda: dtm.datetime.now(dtm.UTC))
    "Time when the event was created"

    class Settings(BeanieDocument.Settings):
        name = "events"


document_models = [Event]
