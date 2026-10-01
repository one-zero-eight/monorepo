import datetime as dtm
import logging

from anyio import to_thread
from beanie import PydanticObjectId
from pydantic import Field, model_validator
from pymongo.errors import DuplicateKeyError

from src.board_games.modules.board_games.photos_repo import photos_repo
from src.board_games.mongo import BoardGame, Reservation, ReservationStatus
from src.board_games.schemas import (
    BoardGameWithAvailabilityOut,
    BoardGameWithStorageAvailabilityOut,
)
from src.common_pydantic import BaseSchema

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (ReservationStatus.RESERVED, ReservationStatus.TAKEN)
PHOTO_SIZES = (None, 512)

# --------------------------------------------------------------------------- #
# Input schemas
# --------------------------------------------------------------------------- #


class CreateBoardGame(BaseSchema):
    title: str
    description: str | None = None
    total_copies: int = Field(default=1, ge=1)


class UpdateBoardGame(BaseSchema):
    title: str | None = None
    description: str | None = None
    total_copies: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CreateReservation(BaseSchema):
    tg_alias: str = Field(min_length=1)
    return_date: dtm.date
    when_available: str | None = None
    comments: str | None = None


class UpdateReservation(BaseSchema):
    tg_alias: str | None = None
    return_date: dtm.date | None = None
    when_available: str | None = None
    comments: str | None = None


class UpdateReservationAdmin(BaseSchema):
    status: ReservationStatus | None = None
    borrower_name: str | None = None
    return_date: dtm.date | None = None


# --------------------------------------------------------------------------- #
# Errors (mapped to HTTP responses in routes.py)
# --------------------------------------------------------------------------- #


class BoardGameAlreadyExistsError(Exception):
    """Raised when a board game with the same unique field already exists."""


class BoardGameNotFoundError(Exception):
    """Raised when a board game does not exist."""


class ReservationNotFoundError(Exception):
    """Raised when a reservation does not exist (or does not belong to the user)."""


class ReservationConflictError(Exception):
    """Raised when the requested reservation operation is not allowed in the current state."""


# --------------------------------------------------------------------------- #
# Board games
# --------------------------------------------------------------------------- #


async def create(data: CreateBoardGame) -> BoardGame:
    try:
        return await BoardGame.model_validate(data, from_attributes=True).create()
    except DuplicateKeyError as exc:
        raise BoardGameAlreadyExistsError() from exc


async def read(id: PydanticObjectId) -> BoardGame | None:
    return await BoardGame.get(id)


async def read_all() -> list[BoardGame]:
    return await BoardGame.all().to_list()


async def update(id: PydanticObjectId, update_data: UpdateBoardGame) -> BoardGame | None:
    board_game = await BoardGame.get(id)
    if not board_game:
        return None

    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        return board_game

    try:
        await board_game.update({"$set": update_dict})
    except DuplicateKeyError as exc:
        raise BoardGameAlreadyExistsError() from exc
    return await BoardGame.get(id)


def delete_photo_blobs(photo_file_id: str) -> None:
    """Best-effort removal of all photo sizes. Idempotent.

    Blocking (MinIO client): call via ``to_thread.run_sync``.
    """
    for size in PHOTO_SIZES:
        try:
            photos_repo.delete(photo_file_id, size)
        except Exception:
            # Don't fail the whole operation because a blob was already gone
            # or the storage hiccupped.
            logger.exception("Failed to delete photo blob %s size=%s", photo_file_id, size)


async def delete(id: PydanticObjectId) -> bool:
    game = await BoardGame.get(id)
    if game is None:
        return False

    photo_file_id = game.photo_file_id  # capture before the doc is gone

    await Reservation.find(Reservation.board_game_id == str(id)).delete()
    result = await game.delete()
    deleted = bool(result and result.deleted_count > 0)

    if deleted and photo_file_id:
        await to_thread.run_sync(delete_photo_blobs, photo_file_id)

    return deleted


# --------------------------------------------------------------------------- #
# Availability
# --------------------------------------------------------------------------- #


async def _count_reservations_by_game() -> dict[str, tuple[int, int]]:
    """Return ``{board_game_id: (active_count, taken_count)}`` using a single aggregation."""
    rows = await Reservation.aggregate(
        [
            {"$match": {"status": {"$in": [s.value for s in ACTIVE_STATUSES]}}},
            {
                "$group": {
                    "_id": {"game": "$board_game_id", "status": "$status"},
                    "count": {"$sum": 1},
                }
            },
        ]
    ).to_list()

    counts: dict[str, tuple[int, int]] = {}
    for row in rows:
        game_id = row["_id"]["game"]
        status = row["_id"]["status"]
        active, taken = counts.get(game_id, (0, 0))
        active += row["count"]
        if status == ReservationStatus.TAKEN:
            taken += row["count"]
        counts[game_id] = (active, taken)
    return counts


async def read_all_with_availability() -> list[BoardGameWithAvailabilityOut]:
    games = await read_all()
    counts = await _count_reservations_by_game()
    return [BoardGameWithAvailabilityOut.from_document(g, active=counts.get(str(g.id), (0, 0))[0]) for g in games]


async def read_all_with_storage_availability() -> list[BoardGameWithStorageAvailabilityOut]:
    games = await read_all()
    counts = await _count_reservations_by_game()
    result = []
    for g in games:
        active, taken = counts.get(str(g.id), (0, 0))
        result.append(BoardGameWithStorageAvailabilityOut.from_document(g, active=active, taken=taken))
    return result


async def _count_active_reservations(board_game_id: str) -> int:
    return await Reservation.find(
        {
            "board_game_id": board_game_id,
            "status": {"$in": [s.value for s in ACTIVE_STATUSES]},
        }
    ).count()


# --------------------------------------------------------------------------- #
# Reservations — reads
# --------------------------------------------------------------------------- #


async def read_reservations() -> list[Reservation]:
    return await Reservation.all().to_list()


async def read_current_reservations() -> list[Reservation]:
    return await Reservation.find({"status": {"$in": [s.value for s in ACTIVE_STATUSES]}}).to_list()


async def read_board_games_reservations(board_game_id: PydanticObjectId) -> list[Reservation] | None:
    board_game = await BoardGame.get(board_game_id)
    if not board_game:
        return None

    return await Reservation.find(Reservation.board_game_id == str(board_game_id)).to_list()


async def read_user_reservations(user_innohassle_id: str) -> list[Reservation]:
    return await Reservation.find(Reservation.user_innohassle_id == user_innohassle_id).to_list()


async def read_user_current_reservations(user_innohassle_id: str) -> list[Reservation]:
    return await Reservation.find(
        Reservation.user_innohassle_id == user_innohassle_id,
        {"status": {"$in": [s.value for s in ACTIVE_STATUSES]}},
    ).to_list()


# --------------------------------------------------------------------------- #
# Reservations — user operations
# --------------------------------------------------------------------------- #


async def create_reservation_for_game(
    board_game_id: PydanticObjectId,
    user_innohassle_id: str,
    user_email: str,
    data: CreateReservation,
) -> Reservation:
    game = await BoardGame.get(board_game_id)
    if game is None:
        raise BoardGameNotFoundError()

    existing = await Reservation.find_one(
        Reservation.board_game_id == str(game.id),
        Reservation.user_innohassle_id == user_innohassle_id,
        Reservation.status == ReservationStatus.RESERVED,
    )
    if existing:
        raise ReservationConflictError("You already have an active reservation for this board game")

    # NOTE: check-then-insert is not atomic; concurrent requests can oversubscribe a game.
    active = await _count_active_reservations(str(game.id))
    if active >= game.total_copies:
        raise ReservationConflictError("No copies available")

    return await Reservation(
        board_game_id=str(game.id),
        user_innohassle_id=user_innohassle_id,
        user_email=user_email,
        **data.model_dump(),
    ).create()


async def _get_own_reservation(id: PydanticObjectId, user_innohassle_id: str) -> Reservation:
    reservation = await Reservation.get(id)
    # Same error for "missing" and "not yours" so ids can't be probed.
    if reservation is None or reservation.user_innohassle_id != user_innohassle_id:
        raise ReservationNotFoundError()
    return reservation


async def update_user_reservation(
    id: PydanticObjectId, user_innohassle_id: str, data: UpdateReservation
) -> Reservation:
    reservation = await _get_own_reservation(id, user_innohassle_id)
    if reservation.status != ReservationStatus.RESERVED:
        raise ReservationConflictError("Only reservations in 'reserved' status can be edited")

    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return reservation

    for field, value in update_dict.items():
        setattr(reservation, field, value)
    await reservation.save()
    return reservation


async def delete_user_reservation(id: PydanticObjectId, user_innohassle_id: str) -> None:
    reservation = await _get_own_reservation(id, user_innohassle_id)
    if reservation.status != ReservationStatus.RESERVED:
        raise ReservationConflictError("Only reservations in 'reserved' status can be cancelled")
    await reservation.delete()


# --------------------------------------------------------------------------- #
# Reservations — admin operations
# --------------------------------------------------------------------------- #


async def update_reservation_admin(
    id: PydanticObjectId,
    status: ReservationStatus | None,
    borrower_name: str | None,
    return_date: dtm.date | None,
) -> Reservation | None:
    reservation = await Reservation.get(id)
    if reservation is None:
        return None

    if status:
        reservation.status = status
        if status == ReservationStatus.TAKEN and borrower_name is not None:
            reservation.borrower_name = borrower_name

    if return_date:
        reservation.return_date = return_date

    await reservation.save()
    return reservation


async def delete_reservation_admin(id: PydanticObjectId) -> bool:
    reservation = await Reservation.get(id)
    if reservation is None:
        return False
    result = await reservation.delete()
    return bool(result and result.deleted_count > 0)
