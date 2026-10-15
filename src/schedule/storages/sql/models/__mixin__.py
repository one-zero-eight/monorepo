__all__ = [
    "DescriptionMixin",
    "IdMixin",
    "NameMixin",
    "UpdateCreateDateTimeMixin",
]

import datetime as dtm

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


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
