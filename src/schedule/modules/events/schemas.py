__all__ = ["AddEventPatch", "CreateEvent", "UpdateEvent", "UpdateEventPatch", "ViewEvent", "ViewEventPatch"]

import datetime as dtm

from icalendar import vRecur
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateEvent(BaseModel):
    name: str
    description: str | None = None
    patches: list[AddEventPatch] = Field(default_factory=list)


class ViewEvent(BaseModel):
    id: int
    name: str
    description: str | None = None

    patches: list[ViewEventPatch] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class UpdateEvent(BaseModel):
    name: str | None = None
    description: str | None = None


class AddEventPatch(BaseModel):
    type: str = "create"

    # --- .ics fields --- #
    summary: str
    description: str | None = None
    location: str | None = None

    dtstart: dtm.datetime
    dtend: dtm.datetime

    rrule: str | dict | None = None

    @field_validator("rrule", mode="before")
    @classmethod
    def _validate_rrule(cls, v) -> str:
        if isinstance(v, vRecur):
            v = v.to_ical().decode()
        elif isinstance(v, dict):
            v = vRecur(**v).to_ical().decode()
        elif isinstance(v, str):
            # validate ical string
            _ = vRecur(vRecur.from_ical(v))
            reverse = _.to_ical().decode()
            if v.upper() != reverse.upper():
                raise ValueError(f"Invalid ical string {v!r}")
        return v


class ViewEventPatch(BaseModel):
    id: int
    parent_id: int
    type: str

    # --- .ics fields --- #
    summary: str
    description: str | None = None
    location: str | None = None

    dtstart: dtm.datetime
    dtend: dtm.datetime

    rrule: vRecur | None = None

    @field_validator("rrule", mode="before")
    @classmethod
    def _validate_rrule(cls, v):
        if isinstance(v, str):
            return vRecur.from_ical(v)
        return v

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class UpdateEventPatch(BaseModel):
    # --- .ics fields --- #
    summary: str | None = None
    description: str | None = None
    location: str | None = None

    dtstart: dtm.datetime | None = None
    dtend: dtm.datetime | None = None

    rrule: vRecur | None = None

    @field_validator("rrule", mode="before")
    @classmethod
    def _validate_rrule(cls, v):
        if isinstance(v, str):
            return vRecur.from_ical(v)
        return v

    model_config = ConfigDict(arbitrary_types_allowed=True)


# Update forward refs
CreateEvent.model_rebuild()
ViewEvent.model_rebuild()
UpdateEvent.model_rebuild()
