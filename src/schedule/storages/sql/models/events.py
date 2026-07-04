__all__ = ["Event", "EventPatch"]

import datetime as dtm
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.schedule.storages.sql.models import Base
from src.schedule.storages.sql.models.__mixin__ import (
    DescriptionMixin,
    IdMixin,
    NameMixin,
    UpdateCreateDateTimeMixin,
    ownerships_mixin_factory,
)

if TYPE_CHECKING:
    from src.schedule.storages.sql.models.event_groups import EventGroup


class Event(
    Base, IdMixin, NameMixin, DescriptionMixin, UpdateCreateDateTimeMixin, ownerships_mixin_factory("events", Base)
):
    """
    Create new .icalendar event
        - summary
        - dtstart
        - dtend OR duration
        - rrule [optional]
        - description [optional]
        - location [optional]
        - organizer [optional]
        - attendees [optional]
        - categories [optional]
    """

    __tablename__ = "events"

    patches: Mapped[list[EventPatch]] = relationship(
        "EventPatch", back_populates="parent", cascade="all, delete-orphan", lazy="selectin"
    )

    event_groups: Mapped[list[EventGroup]] = relationship(
        "EventGroup", secondary="events_x_event_groups", back_populates="events", lazy="selectin"
    )


class EventPatch(Base, IdMixin):
    """
        Patch for .icalendar event
        - order-id
    я
    """

    __tablename__ = "event_patches"

    parent_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    parent: Mapped[Event] = relationship("Event", back_populates="patches", lazy="joined")
    type = mapped_column(String(255), nullable=False, default="create")

    # --- .ics fields --- #
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    location: Mapped[str] = mapped_column(String(255), nullable=True)

    dtstart: Mapped[dtm.datetime] = mapped_column()
    dtend: Mapped[dtm.datetime] = mapped_column()

    rrule: Mapped[str] = mapped_column()


class EventXEventGroup(Base):
    __tablename__ = "events_x_event_groups"

    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, primary_key=True)
    event_group_id: Mapped[int] = mapped_column(ForeignKey("event_groups.id"), nullable=False, primary_key=True)
