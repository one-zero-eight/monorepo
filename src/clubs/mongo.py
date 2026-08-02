__all__ = [
    "Club",
    "ClubSchema",
    "ClubType",
    "LinkSchema",
    "LinkType",
    "PendingClubUpdate",
    "User",
    "UserRole",
    "UserSchema",
    "document_models",
]

from enum import StrEnum
from typing import ClassVar

from pydantic import Field
from pymongo import IndexModel

from src.common_beanie import BeanieDocument
from src.common_pydantic import BaseSchema


class LinkType(StrEnum):
    TELEGRAM_CHANNEL = "telegram_channel"
    TELEGRAM_CHAT = "telegram_chat"
    TELEGRAM_USER = "telegram_user"
    EXTERNAL_URL = "external_url"


class LinkSchema(BaseSchema):
    type: LinkType
    link: str
    label: str | None = None


class ClubType(StrEnum):
    TECH = "tech"
    SPORT = "sport"
    HOBBY = "hobby"
    ART = "art"


class PendingClubUpdate(BaseSchema):
    title: str | None = None
    short_description: str | None = None
    description: str | None = None
    logo_file_id: str | None = None
    type: ClubType | None = None
    links: list[LinkSchema] | None = None
    leader_innohassle_id: str | None = None
    sport_id: str | None = None


class ClubSchema(BaseSchema):
    is_active: bool = True
    "False if the club is closed"
    slug: str
    "Alias for using in URL and identification"
    title: str
    "Title of the club"
    short_description: str
    "Short description for displaying in cards"
    description: str
    "Long description of the club"
    logo_file_id: str | None = None
    "File ID of the logo picture"
    type: ClubType
    "Type of the club"
    leader_innohassle_id: str | None = None
    "Club leader"
    links: list[LinkSchema] = Field(default_factory=list)
    "Club resources links (channels, chats, websites)"
    sport_id: str | None = None
    "ID of sport type in InnoSport system (None if the club is not sport)"
    pending_update: PendingClubUpdate | None = None
    "Pending update proposed by the club leader, waiting for admin approval"


class Club(ClubSchema, BeanieDocument):
    class Settings(BeanieDocument.Settings):
        indexes: ClassVar = [IndexModel("slug", unique=True)]


class UserRole(StrEnum):
    DEFAULT = "default"
    ADMIN = "admin"


class UserSchema(BaseSchema):
    innohassle_id: str
    "ID of the InNoHassle Accounts user"
    role: UserRole = UserRole.DEFAULT
    "System role of the user"


class User(UserSchema, BeanieDocument):
    class Settings(BeanieDocument.Settings):
        indexes: ClassVar = [IndexModel("innohassle_id", unique=True)]


document_models = [Club, User]
