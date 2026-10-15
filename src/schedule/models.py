__all__ = [
    "Base",
    "DescriptionMixin",
    "EventGroup",
    "EventGroupTagAssociation",
    "IdMixin",
    "LinkedCalendar",
    "NameMixin",
    "Tag",
    "UpdateCreateDateTimeMixin",
    "User",
    "UserScheduleKeys",
    "UserXFavoriteEventGroup",
    "UserXHiddenEventGroup",
]

import datetime as dtm
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, false, func
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[int] = mapped_column(primary_key=True)


class UpdateCreateDateTimeMixin:
    updated_at: Mapped[dtm.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[dtm.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class NameMixin:
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class DescriptionMixin:
    description: Mapped[str] = mapped_column(Text, nullable=True)


class Tag(Base, IdMixin, NameMixin, DescriptionMixin):
    __tablename__ = "tags"

    alias: Mapped[str] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(nullable=True)
    satellite: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)

    __table_args__ = (UniqueConstraint("alias", "type"),)


class EventGroup(Base, IdMixin, NameMixin, DescriptionMixin, UpdateCreateDateTimeMixin):
    __tablename__ = "event_groups"
    alias: Mapped[str] = mapped_column(String(255), unique=True)
    path: Mapped[str] = mapped_column(nullable=True, unique=True)
    satellite: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)

    tags_association: Mapped[list[EventGroupTagAssociation]] = relationship("EventGroupTagAssociation", lazy="selectin")
    tags: AssociationProxy[list[Tag]] = association_proxy("tags_association", "tag")


class EventGroupTagAssociation(Base):
    __tablename__ = "event_groups_x_tags"

    object_id: Mapped[int] = mapped_column(ForeignKey("event_groups.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    tag: Mapped[Tag] = relationship("Tag", lazy="joined")


class UserXFavoriteEventGroup(Base):
    __tablename__ = "users_x_favorite_groups"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_alias: Mapped[str] = mapped_column(String(255), primary_key=True)


class UserXHiddenEventGroup(Base):
    __tablename__ = "users_x_hidden_groups"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_alias: Mapped[str] = mapped_column(String(255), primary_key=True)


class User(Base, IdMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(nullable=True)
    innohassle_id: Mapped[str] = mapped_column(unique=True, nullable=True)
    email: Mapped[str] = mapped_column(unique=True)

    favorites_association: Mapped[list[UserXFavoriteEventGroup]] = relationship(
        "UserXFavoriteEventGroup", cascade="all, delete-orphan", passive_deletes=True
    )

    favorite_event_groups: AssociationProxy[list[str]] = association_proxy(
        "favorites_association",
        "group_alias",
    )
    hidden_event_groups_association: Mapped[list[UserXHiddenEventGroup]] = relationship(
        "UserXHiddenEventGroup",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    hidden_event_groups: AssociationProxy[list[str]] = association_proxy(
        "hidden_event_groups_association",
        "group_alias",
    )

    linked_calendars: Mapped[list[LinkedCalendar]] = relationship(
        "LinkedCalendar",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    music_room_hidden: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=false())
    sports_hidden: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=false())
    moodle_hidden: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=false())
    events_hidden: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=false())
    room_bookings_hidden: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=false())
    moodle_userid: Mapped[int | None] = mapped_column(nullable=True)
    moodle_calendar_authtoken: Mapped[str | None] = mapped_column(nullable=True)


class UserScheduleKeys(Base, IdMixin):
    __tablename__ = "user_schedule_keys"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    access_key: Mapped[str] = mapped_column(nullable=False, index=True)
    resource_path: Mapped[str] = mapped_column(nullable=False)


class LinkedCalendar(Base, IdMixin, NameMixin, DescriptionMixin):
    __tablename__ = "linked_calendars"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(255), nullable=False)

    url: Mapped[str] = mapped_column(nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)

    user: Mapped[User] = relationship(
        "User",
        back_populates="linked_calendars",
    )

    color: Mapped[str] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "alias", name="unique_user_id_alias"),)
