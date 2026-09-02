import datetime as dtm

from beanie import PydanticObjectId
from pydantic import Field

from src.board_games.mongo import BoardGame, Reservation, ReservationStatus
from src.common_pydantic import BaseSchema


class CreateBoardGame(BaseSchema):
    title: str
    description: str | None = None
    total_copies: int = Field(default=1, ge=1)


class UpdateBoardGame(BaseSchema):
    title: str | None = None
    description: str | None = None
    total_copies: int | None = Field(default=None, ge=1)


class BoardGameWithAvailability(BoardGame):
    available_copies: int


class BoardGameWithStorageAvailability(BoardGame):
    available_copies: int
    available_in_storage: int


class CreateReservationResult(Reservation):
    pass


class CreateReservation(BaseSchema):
    tg_alias: str | None = None
    return_date: dtm.date | None = None
    when_available: str | None = None
    comments: str | None = None


class UpdateReservation(BaseSchema):
    tg_alias: str | None = None
    return_date: dtm.date | None = None
    when_available: str | None = None
    comments: str | None = None


class UpdateReservationStatus(BaseSchema):
    status: ReservationStatus
    borrower_name: str | None


async def create(data: CreateBoardGame) -> BoardGame:
    return await BoardGame.model_validate(data, from_attributes=True).create()


async def read(id: PydanticObjectId) -> BoardGame | None:
    return await BoardGame.get(id)


async def update(id: PydanticObjectId, update_data: UpdateBoardGame) -> BoardGame | None:
    board_game = await BoardGame.get(id)
    if not board_game:
        return None

    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        return board_game

    await board_game.update({"$set": update_dict})
    return await BoardGame.get(id)


async def read_all() -> list[BoardGame]:
    return await BoardGame.all().to_list()


async def delete(id: PydanticObjectId) -> bool:
    game = await BoardGame.get(id)
    if game is None:
        return False
    await Reservation.find(Reservation.board_game_id == str(id)).delete()
    result = await game.delete()
    return bool(result and result.deleted_count > 0)


async def count_active_reservations(board_game_id: str) -> int:
    return await Reservation.find(
        {
            "board_game_id": board_game_id,
            "status": {"$in": [ReservationStatus.RESERVED, ReservationStatus.TAKEN]},
        }
    ).count()


async def count_taken_reservations(board_game_id: str) -> int:
    return await Reservation.find(
        {
            "board_game_id": board_game_id,
            "status": ReservationStatus.TAKEN,
        }
    ).count()


async def read_all_with_availability() -> list[BoardGameWithAvailability]:
    games = await read_all()
    result: list[BoardGameWithAvailability] = []
    for game in games:
        active = await count_active_reservations(str(game.id))
        result.append(
            BoardGameWithAvailability.model_validate(
                {**game.model_dump(), "id": game.id, "available_copies": max(game.total_copies - active, 0)}
            )
        )
    return result


async def read_all_with_storage_availability() -> list[BoardGameWithStorageAvailability]:
    games = await read_all()
    result: list[BoardGameWithStorageAvailability] = []
    for game in games:
        taken = await count_taken_reservations(str(game.id))
        active = await count_active_reservations(str(game.id))
        result.append(
            BoardGameWithStorageAvailability.model_validate(
                {
                    **game.model_dump(),
                    "id": game.id,
                    "available_copies": max(game.total_copies - active, 0),
                    "available_in_storage": max(game.total_copies - taken, 0),
                }
            )
        )
    return result


async def create_reservation(
    game: BoardGame,
    user_innohassle_id: str,
    user_email: str,
    data: CreateReservation,
) -> Reservation | None:
    existing_reservation = await Reservation.find_one(
        Reservation.board_game_id == str(game.id),
        Reservation.user_innohassle_id == user_innohassle_id,
        Reservation.status == ReservationStatus.RESERVED,
    )

    if existing_reservation:
        return None

    active = await count_active_reservations(str(game.id))
    if active >= game.total_copies:
        return None
    return await Reservation(
        board_game_id=str(game.id),
        user_innohassle_id=user_innohassle_id,
        user_email=user_email,
        **data.model_dump(),
    ).create()


async def read_reservations() -> list[Reservation]:
    return await Reservation.all().to_list()


async def read_current_reservations() -> list[Reservation]:
    return await Reservation.find({"status": {"$in": [ReservationStatus.RESERVED, ReservationStatus.TAKEN]}}).to_list()


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
        {"status": {"$in": [ReservationStatus.RESERVED, ReservationStatus.TAKEN]}},
    ).to_list()


async def read_reservation(id: PydanticObjectId) -> Reservation | None:
    return await Reservation.get(id)


async def update_reservation(id: PydanticObjectId, data: UpdateReservation) -> Reservation | None:
    update_dict = data.model_dump(exclude_unset=True)
    if not update_dict:
        return await Reservation.get(id)

    reservation = await Reservation.get(id)
    if not reservation:
        return None

    await reservation.update({"$set": update_dict})
    return await Reservation.get(id)


async def delete_reservation(id: PydanticObjectId) -> bool:
    reservation = await Reservation.get(id)
    if reservation is None:
        return False
    result = await reservation.delete()
    return bool(result and result.deleted_count > 0)


async def update_reservation_status(
    id: PydanticObjectId, status: ReservationStatus, borrower_name: str | None
) -> Reservation | None:
    reservation = await Reservation.get(id)
    if reservation is None:
        return None
    reservation.status = status
    if reservation.status == ReservationStatus.TAKEN and borrower_name is not None:
        reservation.borrower_name = borrower_name
    await reservation.save()
    return reservation


# async def lend_reservation(id: PydanticObjectId, borrower_name: str) -> Reservation | None:
#     reservation = await Reservation.get(id)
#     if reservation is None:
#         return None
#     reservation.status = ReservationStatus.TAKEN
#     reservation.borrower_name = borrower_name
#     await reservation.save()
#     return reservation
