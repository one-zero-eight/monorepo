__all__ = [
    "BoardGame",
    "BoardGameSchema",
    "Reservation",
    "ReservationSchema",
    "ReservationStatus",
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


class BoardGameSchema(BaseSchema):
    title: str
    "Board game title"
    description: str | None = None
    "Short board game description"
    photo_url: str | None = None
    "Board game photo URL"
    total_copies: int = Field(default=1, ge=1)
    "Number of copies available for reservation"


class BoardGame(BoardGameSchema, BeanieDocument):
    class Settings(BeanieDocument.Settings):
        indexes: ClassVar = [IndexModel("title", unique=True)]


class ReservationStatus(StrEnum):
    RESERVED = "reserved"
    TAKEN = "taken"
    RETURNED = "returned"


class ReservationSchema(BaseSchema):
    board_game_id: str
    "Reserved board game ID"
    user_innohassle_id: str
    "ID of the user who made the reservation"
    user_email: str
    "Email of the user who made the reservation"
    status: ReservationStatus = ReservationStatus.RESERVED
    "Reservation status"
    tg_alias: str | None = None
    "Telegram alias of the user who made the reservation"
    return_date: dtm.date | None = None
    "Expected return date"
    when_available: str | None = None
    "Human-readable availability information"
    comments: str | None = None
    "Reservation comments"
    borrower_name: str | None = None
    "Name saved by admin when the board game is taken"
    created_at: dtm.datetime = Field(default_factory=lambda: dtm.datetime.now(dtm.UTC))
    "Reservation creation time"


class Reservation(ReservationSchema, BeanieDocument):
    class Settings(BeanieDocument.Settings):
        indexes: ClassVar = [
            IndexModel("board_game_id"),
            IndexModel("user_innohassle_id"),
            IndexModel([("board_game_id", 1), ("user_innohassle_id", 1), ("status", 1)]),
        ]


document_models = [User, BoardGame, Reservation]
