__all__ = [
    "CreateEventGroup",
    "CreateEventGroupWithoutTags",
    "ListEventGroupsResponse",
    "UpdateEventGroup",
    "ViewEventGroup",
]

import datetime
from collections.abc import Iterable
from pathlib import PurePath

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schedule.modules.tags.schemas import CreateTag, ViewTag


def _validate_event_group_path(path: str | None) -> str | None:
    if path is None:
        return None

    normalized_path = PurePath(path)
    if normalized_path.is_absolute() or ".." in normalized_path.parts:
        raise ValueError("Path must stay within predefined/ics")
    if normalized_path.name == "" or normalized_path.suffix != ".ics":
        raise ValueError("Path must point to an .ics file inside predefined/ics")

    return path


class CreateEventGroupWithoutTags(BaseModel):
    """
    Represents a group instance to be created.
    """

    alias: str
    name: str
    path: str | None = None
    description: str | None = None

    @field_validator("path")
    def _validate_path(cls, v: str | None):
        return _validate_event_group_path(v)


class CreateEventGroup(CreateEventGroupWithoutTags):
    tags: list[CreateTag] = Field(default_factory=list)


class ViewEventGroup(BaseModel):
    """
    Represents a group instance from the database excluding sensitive information.
    """

    id: int
    alias: str
    updated_at: datetime.datetime
    created_at: datetime.datetime
    path: str | None = None
    name: str | None = None
    description: str | None = None
    tags: list[ViewTag] = Field(default_factory=list)

    # ownerships: list["Ownership"] = Field(default_factory=list)
    @field_validator("tags", mode="before")
    def _validate_tags(cls, v):
        v = list(v) if v else []
        return v

    model_config = ConfigDict(from_attributes=True)


class UpdateEventGroup(BaseModel):
    """
    Represents a group instance to be updated.
    """

    alias: str | None = None
    name: str | None = None
    description: str | None = None
    path: str | None = None

    @field_validator("path")
    def _validate_path(cls, v: str | None):
        return _validate_event_group_path(v)


class ListEventGroupsResponse(BaseModel):
    """
    Represents a list of event groups.
    """

    event_groups: list[ViewEventGroup]

    @classmethod
    def from_iterable(cls, groups: Iterable[ViewEventGroup]) -> ListEventGroupsResponse:
        return cls(event_groups=groups)
