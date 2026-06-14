__all__ = [
    "GoogleFile",
    "GoogleFileSSOBan",
    "GoogleFileSSOJoin",
    "GoogleFileSchema",
    "GoogleFileType",
    "GoogleFileUserRole",
    "UserID",
    "document_models",
]

import datetime as dtm
from typing import ClassVar, Literal

from beanie import PydanticObjectId
from pymongo import IndexModel

from src.common_beanie import BeanieDocument
from src.common_pydantic import BaseSchema

type UserID = PydanticObjectId

type GoogleFileUserRole = Literal["writer", "reader"]
type GoogleFileType = Literal["spreadsheet", "document"]


class GoogleFileSSOJoin(BaseSchema):
    user_id: UserID
    gmail: str
    innomail: str
    role: GoogleFileUserRole
    joined_at: dtm.datetime
    permission_id: str | None


class GoogleFileSSOBan(BaseSchema):
    user_id: UserID
    gmail: str
    innomail: str
    banned_at: dtm.datetime


class GoogleFileSchema(BaseSchema):
    author_id: UserID
    default_role: GoogleFileUserRole
    owner_gmail: str
    owner_permission_id: str
    slug: str
    file_id: str
    file_type: GoogleFileType
    title: str
    expire_at: dtm.datetime | None = None
    sso_joins: list[GoogleFileSSOJoin]
    sso_banned: list[GoogleFileSSOBan]


class GoogleFile(GoogleFileSchema, BeanieDocument):
    class Settings(BeanieDocument.Settings):
        indexes: ClassVar = [
            IndexModel("slug", unique=True),
            IndexModel("file_id"),
            IndexModel("author_id"),
        ]


document_models = [GoogleFile]
