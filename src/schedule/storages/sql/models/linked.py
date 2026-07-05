__all__ = ["LinkedCalendar"]

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.schedule.storages.sql.models.__mixin__ import DescriptionMixin, IdMixin, NameMixin
from src.schedule.storages.sql.models.base import Base

if TYPE_CHECKING:
    from src.schedule.storages.sql.models.users import User


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

    # constraint
    __table_args__ = (UniqueConstraint("user_id", "alias", name="unique_user_id_alias"),)
