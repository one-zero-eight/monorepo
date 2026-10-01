import datetime as dtm

from beanie import PydanticObjectId

from src.board_games.mongo import BoardGame, Reservation, ReservationStatus
from src.common_pydantic import BaseSchema


class BoardGameBase(BaseSchema):
    id: PydanticObjectId
    title: str
    description: str | None
    total_copies: int
    has_photo: bool

    @staticmethod
    def _base_fields(game: BoardGame) -> dict:
        return {
            "id": game.id,
            "title": game.title,
            "description": game.description,
            "total_copies": game.total_copies,
            "has_photo": bool(game.photo_file_id),
        }


class BoardGameOut(BoardGameBase):
    @classmethod
    def from_document(cls, game: BoardGame) -> BoardGameOut:
        return cls(**cls._base_fields(game))


class BoardGameWithAvailabilityOut(BoardGameBase):
    available_copies: int

    @classmethod
    def from_document(cls, game: BoardGame, *, active: int) -> BoardGameWithAvailabilityOut:
        return cls(
            **cls._base_fields(game),
            available_copies=max(game.total_copies - active, 0),
        )


class BoardGameWithStorageAvailabilityOut(BoardGameBase):
    available_copies: int
    available_in_storage: int

    @classmethod
    def from_document(cls, game: BoardGame, *, active: int, taken: int) -> BoardGameWithStorageAvailabilityOut:
        return cls(
            **cls._base_fields(game),
            available_copies=max(game.total_copies - active, 0),
            available_in_storage=max(game.total_copies - taken, 0),
        )


class ReservationOut(BaseSchema):
    id: PydanticObjectId
    board_game_id: str
    user_innohassle_id: str
    user_email: str
    status: ReservationStatus
    tg_alias: str | None
    return_date: dtm.date | None
    when_available: str | None
    comments: str | None
    borrower_name: str | None
    created_at: dtm.datetime

    @classmethod
    def from_document(cls, r: Reservation) -> ReservationOut:
        return cls(
            id=r.id,
            board_game_id=r.board_game_id,
            user_innohassle_id=r.user_innohassle_id,
            user_email=r.user_email,
            status=r.status,
            tg_alias=r.tg_alias,
            return_date=r.return_date,
            when_available=r.when_available,
            comments=r.comments,
            borrower_name=r.borrower_name,
            created_at=r.created_at,
        )
