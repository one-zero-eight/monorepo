__all__ = ["Tag"]

from typing import Any

from sqlalchemy import JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.schedule.storages.sql.models.__mixin__ import DescriptionMixin, IdMixin, NameMixin
from src.schedule.storages.sql.models.base import Base


class Tag(Base, IdMixin, NameMixin, DescriptionMixin):
    __tablename__ = "tags"

    # parent_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), nullable=True)
    # parent: Mapped["Tag"] = relationship("Tag", remote_side=[id], lazy="selectin")
    # children: Mapped[list["Tag"]] = relationship("Tag", remote_side=[parent_id], lazy="selectin")

    alias: Mapped[str] = mapped_column(nullable=False)
    type: Mapped[str] = mapped_column(nullable=True)
    satellite: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)

    __table_args__ = (UniqueConstraint("alias", "type"),)
