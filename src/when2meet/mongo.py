__all__ = ["Event", "Participant", "document_models"]
import datetime as dtm

from beanie import Document, PydanticObjectId
from pydantic import ConfigDict, Field

from src.common_pydantic import BaseSchema


class Participant(BaseSchema):
    name: str
    "Name of the participant"
    availability: list[dtm.datetime]
    "List of slots the participant is available for"


class Event(Document):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_serialization_defaults_required=True,
    )

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

    # Define id field locally to avoid issues with shared BeanieDocument
    id: PydanticObjectId | None = Field(
        default=None,
        alias="_id",
        serialization_alias="id",
        description="MongoDB document ObjectID",
    )

    class Settings:
        name = "events"
        keep_nulls = False
        max_nesting_depth = 1


document_models = [Event]
