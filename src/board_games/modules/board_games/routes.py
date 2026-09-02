from io import BytesIO

import filetype
from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from PIL import Image
from pydantic import Field
from starlette.responses import RedirectResponse

from src.board_games.dependencies import BOARD_GAMES_ADMIN_AUTH
from src.board_games.mongo import BoardGame, Reservation, ReservationStatus
from src.common_pydantic import BaseSchema
from src.dependencies import INH_TOKEN_AUTH

from . import board_games_repo
from .photos_repo import photos_repo

router = APIRouter(
    tags=["Board Games"],
    route_class=AutoDeriveResponsesAPIRoute,
)
public_router = APIRouter(
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


@router.post("/admin/board-games/{id}/photo")
async def set_board_game_photo(
    id: PydanticObjectId,
    photo_file: UploadFile,
    _: BOARD_GAMES_ADMIN_AUTH,
) -> BoardGame:
    board_game = await board_games_repo.read(id)
    if board_game is None:
        raise HTTPException(status_code=404, detail="Board game not found")

    bytes_ = await photo_file.read()
    content_type = photo_file.content_type
    if content_type is None:  # pragma: no cover
        kind = filetype.guess(bytes_)
        content_type = kind.mime if kind else None
    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail=f"Invalid content type ({content_type})")

    image = Image.open(BytesIO(bytes_))
    full_buf = BytesIO()
    image.save(full_buf, format="WEBP")

    thumbnail = image.copy()
    thumbnail.thumbnail((512, 512), Image.Resampling.LANCZOS)
    thumbnail_buf = BytesIO()
    thumbnail.save(thumbnail_buf, format="WEBP", quality=95, method=6)

    photo_file_id = str(PydanticObjectId())
    photos_repo.put(photo_file_id, None, full_buf.getvalue(), "image/webp")
    photos_repo.put(photo_file_id, 512, thumbnail_buf.getvalue(), "image/webp")
    board_game.photo_file_id = photo_file_id
    await board_game.save()
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


@public_router.get("/board-games/{id}/photo", response_class=RedirectResponse)
async def get_board_game_photo(id: PydanticObjectId) -> RedirectResponse:
    board_game = await board_games_repo.read(id)
    if board_game is None:
        raise HTTPException(status_code=404, detail="Board game not found")
    if not board_game.photo_file_id:
        raise HTTPException(status_code=404, detail="No photo available")
    return RedirectResponse(url=photos_repo.get_url(board_game.photo_file_id, 512))


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
    body: board_games_repo.CreateReservation,
) -> Reservation:
    game = await board_games_repo.read(id)
    if game is None:
        raise HTTPException(status_code=404, detail="Board game not found")
    reservation = await board_games_repo.create_reservation(
        game,
        current_user.innohassle_id,
        current_user.email,
        body,
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
    if existing.status != ReservationStatus.RESERVED:
        raise HTTPException(status_code=409, detail="Reservation is not reserved")
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
    if existing.status != ReservationStatus.RESERVED:
        raise HTTPException(status_code=409, detail="Reservation is not reserved")

    deleted = await board_games_repo.delete_reservation(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Reservation not found")
