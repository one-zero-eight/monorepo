__all__ = ["Player", "document_models"]

import datetime as dtm
from typing import ClassVar

from pydantic import EmailStr, Field
from pymongo import IndexModel

from src.common_beanie import BeanieDocument


class Player(BeanieDocument):
    innohassle_id: str
    nickname: str = "nouname"

    rating: int = 1000
    wins: int = 0
    losses: int = 0

    last_game: dtm.datetime
    status: str = "Beginner"

    class Settings(BeanieDocument.Settings):
        indexes: ClassVar[list[IndexModel]] = [IndexModel("innohassle_id", unique=True)]


class Game(BeanieDocument):
    tour_id: str

    player1_id: str
    player2_id: str

    player1_score: int = Field(ge=0)
    player2_score: int = Field(ge=0)

    class Settings(BeanieDocument.Settings):
        indexes: ClassVar[list[IndexModel]] = [IndexModel("tour_id")]


class Tournament(BeanieDocument):
    id: str
    name: str

    players: list[EmailStr]
    val_games: list[Game] | None = None
    cval_games: list[Game] | None = None

    date: dtm.datetime

    class Settings(BeanieDocument.Settings):
        indexes: ClassVar[list[IndexModel]] = [IndexModel("id", unique=True)]


document_models = [Player, Game, Tournament]
