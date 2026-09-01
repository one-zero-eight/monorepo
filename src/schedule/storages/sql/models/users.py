__all__ = ["User", "UserScheduleKeys"]

from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import ForeignKey, false
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.schedule.storages.sql.models.__mixin__ import IdMixin
from src.schedule.storages.sql.models.base import Base

if TYPE_CHECKING:
    from src.schedule.storages.sql.models.event_groups import UserXFavoriteEventGroup, UserXHiddenEventGroup
    from src.schedule.storages.sql.models.linked import LinkedCalendar


class User(Base, IdMixin):
    __ownerships_tables__: ClassVar[dict[str, object]] = {}
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
    workshops_hidden: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=false())
    room_bookings_hidden: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=false())
    moodle_userid: Mapped[int | None] = mapped_column(nullable=True)
    moodle_calendar_authtoken: Mapped[str | None] = mapped_column(nullable=True)


class UserScheduleKeys(Base, IdMixin):
    __tablename__ = "user_schedule_keys"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    access_key: Mapped[str] = mapped_column(nullable=False, index=True)
    resource_path: Mapped[str] = mapped_column(nullable=False)
