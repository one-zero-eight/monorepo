__all__ = ["Club", "ClubSchema", "ClubType"]

from enum import StrEnum

from pydantic import Field
from pymongo import IndexModel

from src.pydantic_base import BaseSchema
from src.storages.mongo.__base__ import CustomDocument


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


class Club(ClubSchema, CustomDocument):
    class Settings:
        indexes = [
            IndexModel("slug", unique=True),
        ]
