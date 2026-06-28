from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from pydantic import Field

from src.board_games.dependencies import BOARD_GAMES_ADMIN_AUTH
from src.board_games.mongo import BoardGame, Reservation
from src.common_pydantic import BaseSchema
from src.dependencies import INH_TOKEN_AUTH

from . import board_games_repo

router = APIRouter(
    tags=["Board Games"],
    route_class=AutoDeriveResponsesAPIRoute,
)


class LendBoardGame(BaseSchema):
    borrower_name: str = Field(min_length=1)


@router.get("/admin/board-games")
async def get_all_board_games_admin(
    _: BOARD_GAMES_ADMIN_AUTH,
) -> list[board_games_repo.BoardGameWithStorageAvailability]:
    return await board_games_repo.read_all_with_storage_availability()


@router.post("/admin/board-games")
async def add_board_game(body: board_games_repo.CreateBoardGame, _: BOARD_GAMES_ADMIN_AUTH) -> BoardGame:
    return await board_games_repo.create(body)


@router.patch("/admin/board-games/{id}")
async def edit_board_game(
    id: PydanticObjectId,
    body: board_games_repo.UpdateBoardGame,
    _: BOARD_GAMES_ADMIN_AUTH,
) -> BoardGame:
    board_game: BoardGame | None = await board_games_repo.update(id, body)
    if board_game is None:
        raise HTTPException(status_code=404, detail="Board Game not found")
    return board_game


@router.delete("/admin/board-games/{id}")
async def remove_board_game(id: PydanticObjectId, _: BOARD_GAMES_ADMIN_AUTH) -> None:
    deleted = await board_games_repo.delete(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Board game not found")


@router.get("/admin/board-games/{id}/reservations")
async def get_board_games_reservations(id: PydanticObjectId, _: BOARD_GAMES_ADMIN_AUTH) -> list[Reservation]:
    reservations = await board_games_repo.read_board_games_reservations(id)
    if reservations is None:
        raise HTTPException(status_code=404, detail="Board Game not found")
    return reservations


@router.get("/admin/reservations")
async def get_reservations(
    _: BOARD_GAMES_ADMIN_AUTH, how: str = Query("current", pattern="^(current|all)$")
) -> list[Reservation]:
    if how == "current":
        return await board_games_repo.read_current_reservations()
    else:  # type == "all"
        return await board_games_repo.read_reservations()


# @router.post("/admin/reservations/{id}/lend")
# async def lend_boardgame(id: PydanticObjectId, body: LendBoardGame, _: BOARD_GAMES_ADMIN_AUTH) -> Reservation:
#     reservation = await board_games_repo.lend_reservation(id, body.borrower_name)
#     if reservation is None:
#         raise HTTPException(status_code=404, detail="Reservation not found")
#     return reservation


@router.patch("/admin/reservations/{id}/status")
async def edit_reservation_status(
    id: PydanticObjectId,
    body: board_games_repo.UpdateReservationStatus,
    _: BOARD_GAMES_ADMIN_AUTH,
) -> Reservation:
    reservation = await board_games_repo.update_reservation_status(id, body.status, body.borrower_name)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


@router.delete("/admin/reservations/{id}")
async def remove_reservation(id: PydanticObjectId, _: BOARD_GAMES_ADMIN_AUTH) -> None:
    deleted = await board_games_repo.delete_reservation(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Reservation not found")


@router.get("/board-games")
async def get_all_board_games(_: INH_TOKEN_AUTH) -> list[board_games_repo.BoardGameWithAvailability]:
    return await board_games_repo.read_all_with_availability()


@router.get("/users/me/reservations")
async def get_users_reservations(
    current_user: INH_TOKEN_AUTH, how: str = Query("current", pattern="^(current|all)$")
) -> list[Reservation]:
    if how == "current":
        return await board_games_repo.read_user_current_reservations(current_user.innohassle_id)
    else:  # type == "all"
        return await board_games_repo.read_user_reservations(current_user.innohassle_id)


@router.post("/board-games/{id}/reservations")
async def make_reservation(
    id: PydanticObjectId,
    current_user: INH_TOKEN_AUTH,
    body: board_games_repo.CreateReservation | None = None,
) -> Reservation:
    game = await board_games_repo.read(id)
    if game is None:
        raise HTTPException(status_code=404, detail="Board game not found")
    reservation = await board_games_repo.create_reservation(
        game,
        current_user.innohassle_id,
        current_user.email,
        body or board_games_repo.CreateReservation(),
    )
    if reservation is None:
        raise HTTPException(status_code=409, detail="Board game is not available")
    return reservation


@router.patch("/users/me/reservations/{id}")
async def edit_user_reservation(
    id: PydanticObjectId,
    body: board_games_repo.UpdateReservation,
    current_user: INH_TOKEN_AUTH,
) -> Reservation:
    existing = await board_games_repo.read_reservation(id)
    if existing is None or existing.user_innohassle_id != current_user.innohassle_id:
        raise HTTPException(status_code=404, detail="Reservation not found")
    reservation = await board_games_repo.update_reservation(id, body)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


@router.delete("/users/me/reservations/{id}")
async def remove_user_reservation(
    id: PydanticObjectId,
    current_user: INH_TOKEN_AUTH,
) -> None:
    existing = await board_games_repo.read_reservation(id)
    if existing is None or existing.user_innohassle_id != current_user.innohassle_id:
        raise HTTPException(status_code=404, detail="Reservation not found")

    deleted = await board_games_repo.delete_reservation(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Reservation not found")
