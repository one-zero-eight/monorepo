__all__ = ["LinkedCalendarCreate", "LinkedCalendarUpdate", "LinkedCalendarView"]


from pydantic import BaseModel, ConfigDict


class LinkedCalendarView(BaseModel):
    """
    Represents a linked calendar instance from the database excluding sensitive information.
    """

    id: int
    user_id: int
    alias: str
    url: str
    name: str | None = None
    description: str | None = None
    color: str | None = None
    is_active: bool = True
    model_config = ConfigDict(from_attributes=True)


class LinkedCalendarCreate(BaseModel):
    """
    Represents a linked calendar instance to be created.
    """

    alias: str
    url: str
    name: str | None = None
    description: str | None = None
    color: str | None = None
    is_active: bool = True


class LinkedCalendarUpdate(BaseModel):
    """
    Represents a linked calendar instance to be updated.
    """

    alias: str | None = None
    url: str | None = None
    name: str | None = None
    description: str | None = None
    color: str | None = None
    is_active: bool | None = None
