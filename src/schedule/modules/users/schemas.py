__all__ = ["CreateUser", "UpdateUser", "ViewUser", "ViewUserScheduleKey"]


from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schedule.modules.users.linked import LinkedCalendarView


class TargetForExport(StrEnum):
    MUSIC_ROOM = "music-room"
    SPORT = "sport"
    MOODLE = "moodle"
    ROOM_BOOKINGS = "room-bookings"
    WORKSHOPS = "workshops"


class CreateUser(BaseModel):
    """
    Represents a user instance to be created.
    """

    id: int | None = None
    email: str
    innohassle_id: str
    name: str | None = None


class ViewUser(BaseModel):
    """
    Represents a user instance from the database excluding sensitive information.
    """

    id: int
    email: str
    innohassle_id: str | None = None
    name: str | None = None
    favorite_event_groups: list[int] = Field(default_factory=list)
    hidden_event_groups: list[int] = Field(default_factory=list)
    linked_calendars: dict[str, LinkedCalendarView] = Field(default_factory=dict)
    music_room_hidden: bool
    sports_hidden: bool
    moodle_hidden: bool
    workshops_hidden: bool
    room_bookings_hidden: bool
    moodle_userid: int | None = None
    moodle_calendar_authtoken: str | None = None

    @field_validator("linked_calendars", mode="before")
    def calendars_to_dict(cls, v):
        if not isinstance(v, dict):
            keys = [calendar.alias for calendar in v]
            return dict(zip(keys, v))
        return v

    model_config = ConfigDict(from_attributes=True)


class ViewUserScheduleKey(BaseModel):
    """
    Represents a user schedule key.
    """

    user_id: int
    access_key: str
    resource_path: str


class UpdateUser(BaseModel):
    """
    Represents a user instance to be updated.
    """

    email: str | None = None
    name: str | None = None
