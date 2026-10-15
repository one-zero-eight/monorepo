__all__ = ["Tag", "TagOwnership"]

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.schedule.storages.sql.models.__mixin__ import DescriptionMixin, IdMixin, NameMixin
from src.schedule.storages.sql.models.base import Base

if TYPE_CHECKING:
    from src.schedule.storages.sql.models.users import User


class Tag(Base, IdMixin, NameMixin, DescriptionMixin):
    __tablename__ = "tags"

    # parent_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), nullable=True)
    # parent: Mapped["Tag"] = relationship("Tag", remote_side=[id], lazy="selectin")
    # children: Mapped[list["Tag"]] = relationship("Tag", remote_side=[parent_id], lazy="selectin")

    alias: Mapped[str] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(nullable=True)
    satellite: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    ownerships: Mapped[list[TagOwnership]] = relationship("TagOwnership", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("alias", "type"),)


class TagOwnership(Base):
    __tablename__ = "tags_x_ownerships"

    object_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    user: Mapped[User] = relationship("User")
    role_alias: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
