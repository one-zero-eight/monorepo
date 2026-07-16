__all__ = ["Player", "document_models"]

import datetime as dtm
from typing import ClassVar

from pydantic import Field
from pymongo import IndexModel

from src.common_beanie import BeanieDocument


class Player(BeanieDocument):
    innohassle_id: str
    nickname: str = Field(default="nouname", min_length=2, max_length=20)

    rating: int = 1000
    ratings: dict[dtm.datetime, int] = Field(default_factory=dict)
    wins: int = 0
    losses: int = 0

    last_game: dtm.datetime
    status: str = "Beginner"

    class Settings(BeanieDocument.Settings):
        indexes: ClassVar[list[IndexModel]] = [IndexModel("innohassle_id", unique=True)]


class Game(BeanieDocument):
    tour_id: str
    game_id: str

    player1_id: str
    player2_id: str

    player1_score: int = Field(ge=0)
    player2_score: int = Field(ge=0)

    finished: bool = False

    class Settings(BeanieDocument.Settings):
        indexes: ClassVar[list[IndexModel]] = [IndexModel("tour_id")]


class Tournament(BeanieDocument):
    tour_id: str
    name: str

    players: list[str]
    val_games: list[Game] | None = None
    cval_games: list[Game] | None = None

    active: bool = Field(default=False)
    date: dtm.datetime

    val_top: dict[int, str] = Field(default={})
    qual_top: dict[int, str] = Field(default={})

    class Settings(BeanieDocument.Settings):
        name = "Tournament_v2"
        indexes: ClassVar[list[IndexModel]] = [IndexModel("tour_id", unique=True)]


document_models = [Player, Game, Tournament]
