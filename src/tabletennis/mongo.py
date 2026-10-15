__all__ = ["Player", "document_models"]

import datetime as dtm
from typing import ClassVar

from beanie import Document
from pydantic import Field
from pymongo import IndexModel

from src.common_beanie import BeanieDocumentMixin, BeanieSettings


class Player(BeanieDocumentMixin, Document):
    innohassle_id: str
    nickname: str = Field(default="nouname", min_length=2, max_length=20)

    rating: int = 100
    "Newcomers start at 100 until an admin sets their rating manually (any value from 0)."
    ratings: dict[dtm.datetime, int] = Field(default_factory=dict)
    wins: int = 0
    losses: int = 0

    last_game: dtm.datetime
    status: str = "Beginner"
    "Beginner or Advanced. Being an admin is not a status: admins are listed in the settings (admin_emails)."
    placeholder: bool = False
    "A guest created by an admin for someone without an account. Merged into the real player once they register."

    class Settings(BeanieSettings):
        indexes: ClassVar[list[IndexModel]] = [IndexModel("innohassle_id", unique=True)]


class Game(BeanieDocumentMixin, Document):
    tour_id: str
    game_id: str

    player1_id: str
    player2_id: str

    player1_score: int = Field(ge=0)
    player2_score: int = Field(ge=0)

    finished: bool = False
    finished_at: dtm.datetime | None = None
    "When the result was recorded. Games finished before this field existed only have the ObjectId creation time."

    player1_delta: int | None = None
    "Rating change applied to player1 when the game was finished. Needed to roll it back on a score correction."
    player2_delta: int | None = None

    player1_promoted: bool = False
    "Whether this game promoted player1 to Advanced. A score correction takes the promotion back."
    player2_promoted: bool = False

    class Settings(BeanieSettings):
        indexes: ClassVar[list[IndexModel]] = [IndexModel("tour_id")]


class Tournament(BeanieDocumentMixin, Document):
    tour_id: str
    name: str

    players: list[str]
    val_games: list[Game] | None = None
    cval_games: list[Game] | None = None

    active: bool = Field(default=False)
    date: dtm.datetime

    val_top: dict[int, str] = Field(default={})
    qual_top: dict[int, str] = Field(default={})

    groups: dict[str, list[str]] = Field(default_factory=dict)
    "Validation-stage groups: group name -> innohassle_ids. Round robin is played inside each group."
    groups_locked: bool = Field(default=False)
    qual_seeding: list[str] = Field(default_factory=list)
    "Qualification bracket seeding (innohassle_ids, 1st seed first). Fixed once qualification starts."

    bonus_applied: bool = Field(default=False)

    class Settings(BeanieSettings):
        name = "Tournament_v2"
        indexes: ClassVar[list[IndexModel]] = [IndexModel("tour_id", unique=True)]


document_models = [Player, Game, Tournament]
