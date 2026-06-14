__all__ = [
    "Link",
    "LinkSchema",
    "User",
    "UserRole",
    "UserSchema",
    "document_models",
]

import datetime as dtm
from enum import StrEnum
from typing import ClassVar

from pydantic import Field
from pymongo import IndexModel

from src.common_beanie import BeanieDocument
from src.common_pydantic import BaseSchema


class LinkSchema(BaseSchema):
    slug: str
    form_url: str
    owner_innohassle_id: str
    created_at: dtm.datetime


class Link(LinkSchema, BeanieDocument):
    created_at: dtm.datetime = Field(default_factory=lambda: dtm.datetime.now(tz=dtm.UTC))

    class Settings(BeanieDocument.Settings):
        indexes: ClassVar = [
            IndexModel("slug", unique=True),
            IndexModel("owner_innohassle_id"),
            IndexModel([("owner_innohassle_id", 1), ("form_url", 1)], unique=True),
        ]


class UserRole(StrEnum):
    DEFAULT = "default"
    ADMIN = "admin"


class UserSchema(BaseSchema):
    innohassle_id: str
    role: UserRole = UserRole.DEFAULT


class User(UserSchema, BeanieDocument):
    class Settings(BeanieDocument.Settings):
        indexes: ClassVar = [
            IndexModel("innohassle_id", unique=True),
        ]


document_models = [Link, User]
