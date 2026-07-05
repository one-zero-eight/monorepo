__all__ = [
    "DescriptionMixin",
    "IdMixin",
    "NameMixin",
    "UpdateCreateDateTimeMixin",
    "ownerships_mixin_factory",
    "tags_mixin_factory",
]

import datetime as dtm
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship


def tags_mixin_factory(tablename: str, base: type[Any]):
    from src.schedule.storages.sql.models.tags import Tag

    class Mixin:
        class TagAssociation(base):
            __tablename__ = f"{tablename}_x_tags"
            object_id: Mapped[int] = mapped_column(ForeignKey(f"{tablename}.id", ondelete="CASCADE"), primary_key=True)
            tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
            tag: Mapped[Tag] = relationship(lazy="joined")

        Tag.__tags_associations__[tablename] = TagAssociation

        @declared_attr
        def tags_association(cls) -> Mapped[list[Mixin.TagAssociation]]:  # noqa: N805
            return relationship(cls.TagAssociation, lazy="selectin")

        @declared_attr
        def tags(cls) -> AssociationProxy[list[Tag]]:  # noqa: N805
            return association_proxy("tags_association", "tag")

    return Mixin


def ownerships_mixin_factory(tablename: str, base: type[Any]):
    from src.schedule.storages.sql.models.users import User

    class Mixin:
        Ownership = type(
            f"Ownership_{tablename}",
            (base,),
            {
                "__tablename__": f"{tablename}_x_ownerships",
                "object_id": mapped_column(ForeignKey(f"{tablename}.id"), primary_key=True),
                "user_id": mapped_column(ForeignKey(User.id), primary_key=True),
                "user": relationship("User"),
                "role_alias": mapped_column(String(255), nullable=False, default="default"),
            },
        )
        User.__ownerships_tables__[tablename] = Ownership.__table__

        @declared_attr
        def ownerships(cls) -> Mapped[list[Mixin.Ownership]]:  # noqa: N805
            return relationship(cls.Ownership, cascade="all, delete-orphan")

    return Mixin


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
