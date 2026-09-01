__all__ = ["EventGroup", "UserXFavoriteEventGroup", "UserXHiddenEventGroup"]

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.schedule.storages.sql.models import Base
from src.schedule.storages.sql.models.__mixin__ import (
    DescriptionMixin,
    IdMixin,
    NameMixin,
    UpdateCreateDateTimeMixin,
    ownerships_mixin_factory,
    tags_mixin_factory,
)

if TYPE_CHECKING:
    from src.schedule.storages.sql.models.events import Event


class EventGroup(
    Base,
    IdMixin,
    NameMixin,
    DescriptionMixin,
    UpdateCreateDateTimeMixin,
    tags_mixin_factory("event_groups", Base),
    ownerships_mixin_factory("event_groups", Base),
):
    __tablename__ = "event_groups"
    alias: Mapped[str] = mapped_column(String(255), unique=True)
    path: Mapped[str] = mapped_column(nullable=True, unique=True)
    satellite: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)

    events: Mapped[list[Event]] = relationship("Event", secondary="events_x_event_groups")


class UserXFavoriteEventGroup(Base):
    __tablename__ = "users_x_favorite_groups"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_alias: Mapped[str] = mapped_column(String(255), primary_key=True)


class UserXHiddenEventGroup(Base):
    __tablename__ = "users_x_hidden_groups"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_alias: Mapped[str] = mapped_column(String(255), primary_key=True)
