from enum import StrEnum

from pymongo import IndexModel

from src.pydantic_base import BaseSchema
from src.storages.mongo.__base__ import CustomDocument


class UserRole(StrEnum):
    DEFAULT = "default"
    ADMIN = "admin"


class UserSchema(BaseSchema):
    innohassle_id: str
    "ID of the InNoHassle Accounts user"
    role: UserRole = UserRole.DEFAULT
    "System role of the user"


class User(UserSchema, CustomDocument):
    class Settings:
        indexes = [
            IndexModel("innohassle_id", unique=True),
        ]
