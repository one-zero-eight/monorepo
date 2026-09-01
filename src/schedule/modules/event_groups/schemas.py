__all__ = [
    "CreateEventGroup",
    "CreateEventGroupWithoutTags",
    "ListEventGroupsResponse",
    "UpdateEventGroup",
    "ViewEventGroup",
]

import datetime as dtm
from collections.abc import Iterable
from pathlib import PurePath

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schedule.modules.tags.schemas import CreateTag, ViewTag

VIRTUAL_EVENT_GROUP_ALIAS_PREFIXES = ("english-", "teacher-")


def _validate_event_group_path(path: str | None) -> str | None:
    if path is None:
        return None

    normalized_path = PurePath(path)
    if normalized_path.is_absolute() or ".." in normalized_path.parts:
        raise ValueError("Path must stay within predefined/ics")
    if not normalized_path.name or normalized_path.suffix != ".ics":
        raise ValueError("Path must point to an .ics file inside predefined/ics")

    return path


def _validate_local_event_group_alias(alias: str | None) -> str | None:
    if alias is not None and alias.startswith(VIRTUAL_EVENT_GROUP_ALIAS_PREFIXES):
        raise ValueError(f"Aliases starting with {VIRTUAL_EVENT_GROUP_ALIAS_PREFIXES!r} are reserved")
    return alias


class CreateEventGroupWithoutTags(BaseModel):
    """
    Represents a group instance to be created.
    """

    alias: str
    name: str
    path: str | None = None
    description: str | None = None

    @field_validator("alias")
    @classmethod
    def _validate_alias(cls, v: str):
        return _validate_local_event_group_alias(v)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, v: str | None):
        return _validate_event_group_path(v)


class CreateEventGroup(CreateEventGroupWithoutTags):
    tags: list[CreateTag] = Field(default_factory=list)


class ViewEventGroup(BaseModel):
    """
    Represents a group instance from the database excluding sensitive information.
    """

    id: int | None = None
    alias: str
    updated_at: dtm.datetime | None = None
    created_at: dtm.datetime | None = None
    path: str | None = None
    name: str | None = None
    description: str | None = None
    tags: list[ViewTag] = Field(default_factory=list)
    virtual: bool = False

    # ownerships: list["Ownership"] = Field(default_factory=list)
    @field_validator("tags", mode="before")
    @classmethod
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

    @field_validator("alias")
    @classmethod
    def _validate_alias(cls, v: str | None):
        return _validate_local_event_group_alias(v)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, v: str | None):
        return _validate_event_group_path(v)


class ListEventGroupsResponse(BaseModel):
    """
    Represents a list of event groups.
    """

    event_groups: list[ViewEventGroup]

    @classmethod
    def from_iterable(cls, groups: Iterable[ViewEventGroup]) -> ListEventGroupsResponse:
        return cls(event_groups=list(groups))
