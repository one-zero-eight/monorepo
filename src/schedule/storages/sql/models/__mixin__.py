__all__ = [
    "DescriptionMixin",
    "IdMixin",
    "NameMixin",
    "OwnershipsMixinFactory",
    "TagsMixinFactory",
    "UpdateCreateDateTimeMixin",
]

import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column, relationship


def TagsMixinFactory(tablename: str, Base: type[DeclarativeBase]):
    from src.schedule.storages.sql.models.tags import Tag

    class Mixin:
        class TagAssociation(Base):
            __tablename__ = f"{tablename}_x_tags"
            object_id: Mapped[int] = mapped_column(ForeignKey(f"{tablename}.id", ondelete="CASCADE"), primary_key=True)
            tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
            tag: Mapped[Tag] = relationship(lazy="joined")

        Tag.__tags_associations__[tablename] = TagAssociation

        @declared_attr
        def tags_association(cls) -> Mapped[list[TagAssociation]]:
            return relationship(cls.TagAssociation, lazy="selectin")

        @declared_attr
        def tags(cls) -> AssociationProxy[list[Tag]]:
            return association_proxy("tags_association", "tag")

        # @declared_attr
        # def tags(cls) -> Mapped[list["Tag"]]:
        #     return relationship(
        #         "Tag",
        #         lazy="selectin",
        #         secondary=Mixin.TagAssociation.__table__,
        #     )

    return Mixin


def OwnershipsMixinFactory(tablename: str, Base: type[DeclarativeBase]):
    from src.schedule.storages.sql.models.users import User

    class Mixin:
        Ownership = type(
            f"Ownership_{tablename}",
            (Base,),
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
        def ownerships(cls) -> Mapped[list[Ownership]]:
            return relationship(cls.Ownership, cascade="all, delete-orphan")

    return Mixin


class IdMixin:
    id: Mapped[int] = mapped_column(primary_key=True)


class UpdateCreateDateTimeMixin:
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class NameMixin:
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class DescriptionMixin:
    description: Mapped[str] = mapped_column(Text, nullable=True)
