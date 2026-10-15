__all__ = [
    "EventGroup",
    "EventGroupOwnership",
    "EventGroupTagAssociation",
    "UserXFavoriteEventGroup",
    "UserXHiddenEventGroup",
]

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.schedule.storages.sql.models.__mixin__ import (
    DescriptionMixin,
    IdMixin,
    NameMixin,
    UpdateCreateDateTimeMixin,
)
from src.schedule.storages.sql.models.base import Base

if TYPE_CHECKING:
    from src.schedule.storages.sql.models.events import Event
    from src.schedule.storages.sql.models.tags import Tag
    from src.schedule.storages.sql.models.users import User


class EventGroup(Base, IdMixin, NameMixin, DescriptionMixin, UpdateCreateDateTimeMixin):
    __tablename__ = "event_groups"
    alias: Mapped[str] = mapped_column(String(255), unique=True)
    path: Mapped[str] = mapped_column(nullable=True, unique=True)
    satellite: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)

    events: Mapped[list[Event]] = relationship("Event", secondary="events_x_event_groups")
    tags_association: Mapped[list[EventGroupTagAssociation]] = relationship("EventGroupTagAssociation", lazy="selectin")
    tags: AssociationProxy[list[Tag]] = association_proxy("tags_association", "tag")
    ownerships: Mapped[list[EventGroupOwnership]] = relationship("EventGroupOwnership", cascade="all, delete-orphan")


class EventGroupTagAssociation(Base):
    __tablename__ = "event_groups_x_tags"

    object_id: Mapped[int] = mapped_column(ForeignKey("event_groups.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    tag: Mapped[Tag] = relationship("Tag", lazy="joined")


class EventGroupOwnership(Base):
    __tablename__ = "event_groups_x_ownerships"

    object_id: Mapped[int] = mapped_column(ForeignKey("event_groups.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    user: Mapped[User] = relationship("User")
    role_alias: Mapped[str] = mapped_column(String(255), nullable=False, default="default")


class UserXFavoriteEventGroup(Base):
    __tablename__ = "users_x_favorite_groups"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_alias: Mapped[str] = mapped_column(String(255), primary_key=True)


class UserXHiddenEventGroup(Base):
    __tablename__ = "users_x_hidden_groups"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_alias: Mapped[str] = mapped_column(String(255), primary_key=True)
