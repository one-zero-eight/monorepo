from io import BytesIO

import filetype
from anyio import to_thread
from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from PIL import Image, UnidentifiedImageError
from starlette import status
from starlette.responses import RedirectResponse

from src.board_games.dependencies import BOARD_GAMES_ADMIN_AUTH
from src.board_games.modules.board_games import board_games_repo
from src.board_games.modules.board_games.photos_repo import photos_repo
from src.board_games.schemas import (
    BoardGameOut,
    BoardGameWithAvailabilityOut,
    BoardGameWithStorageAvailabilityOut,
    ReservationOut,
)
from src.dependencies import INH_TOKEN_AUTH

router = APIRouter(
    tags=["Board Games"],
    route_class=AutoDeriveResponsesAPIRoute,
)

# --------------------------------------------------------------------------- #
# Board games — admin
# --------------------------------------------------------------------------- #


@router.get("/admin/board-games")
async def get_all_board_games_admin(
    _: BOARD_GAMES_ADMIN_AUTH,
) -> list[BoardGameWithStorageAvailabilityOut]:
    return await board_games_repo.read_all_with_storage_availability()


@router.post("/admin/board-games")
async def add_board_game(body: board_games_repo.CreateBoardGame, _: BOARD_GAMES_ADMIN_AUTH) -> BoardGameOut:
    try:
        board_game = await board_games_repo.create(body)
    except board_games_repo.BoardGameAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Board game already exists") from exc
    return BoardGameOut.from_document(board_game)


@router.patch("/admin/board-games/{id}")
async def edit_board_game(
    id: PydanticObjectId,
    body: board_games_repo.UpdateBoardGame,
    _: BOARD_GAMES_ADMIN_AUTH,
) -> BoardGameOut:
    try:
        board_game = await board_games_repo.update(id, body)
    except board_games_repo.BoardGameAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Board game already exists") from exc
    if board_game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board game not found")
    return BoardGameOut.from_document(board_game)


@router.delete("/admin/board-games/{id}")
async def remove_board_game(id: PydanticObjectId, _: BOARD_GAMES_ADMIN_AUTH) -> None:
    deleted = await board_games_repo.delete(id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board game not found")


# --------------------------------------------------------------------------- #
# Board game photo
# --------------------------------------------------------------------------- #

ALLOWED_PHOTO_MIME = ("image/jpeg", "image/png", "image/webp")
THUMBNAIL_SIZE = 512


def _process_and_store_photo(bytes_: bytes, photo_file_id: str) -> None:
    """Synchronous: decode, re-encode as WebP + thumbnail, upload both to MinIO.

    Runs in a worker thread so it never blocks the event loop.
    Raises HTTPException on invalid image / storage failure.
    """
    try:
        image = Image.open(BytesIO(bytes_))
        image.load()  # force decode; open() alone is lazy
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image") from exc

    try:
        full_buf = BytesIO()
        image.save(full_buf, format="WEBP", quality=95, method=6)

        thumbnail = image.copy()
        thumbnail.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.Resampling.LANCZOS)
        thumbnail_buf = BytesIO()
        thumbnail.save(thumbnail_buf, format="WEBP", quality=95, method=6)
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image") from exc

    try:
        photos_repo.put(photo_file_id, None, full_buf.getvalue(), "image/webp")
        photos_repo.put(photo_file_id, THUMBNAIL_SIZE, thumbnail_buf.getvalue(), "image/webp")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to store image") from exc


@router.post("/admin/board-games/{id}/photo")
async def set_board_game_photo(
    id: PydanticObjectId,
    photo_file: UploadFile,
    _: BOARD_GAMES_ADMIN_AUTH,
) -> BoardGameOut:
    board_game = await board_games_repo.read(id)
    if board_game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board game not found")

    bytes_ = await photo_file.read()
    content_type = photo_file.content_type
    if content_type is None:  # pragma: no cover
        kind = filetype.guess(bytes_)
        content_type = kind.mime if kind else None
    if content_type not in ALLOWED_PHOTO_MIME:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid content type ({content_type})")

    photo_file_id = str(PydanticObjectId())
    old_photo_file_id = board_game.photo_file_id

    await to_thread.run_sync(_process_and_store_photo, bytes_, photo_file_id)

    board_game.photo_file_id = photo_file_id
    try:
        await board_game.save()
    except Exception:
        # Newly uploaded blobs are now orphaned; best-effort cleanup, then re-raise.
        await to_thread.run_sync(board_games_repo.delete_photo_blobs, photo_file_id)
        raise

    # DB first, blobs second. Old blobs are only removed once the document
    # points at the new ones.
    if old_photo_file_id and old_photo_file_id != photo_file_id:
        await to_thread.run_sync(board_games_repo.delete_photo_blobs, old_photo_file_id)

    return BoardGameOut.from_document(board_game)


# --------------------------------------------------------------------------- #
# Reservations — admin
# --------------------------------------------------------------------------- #


@router.get("/admin/board-games/{id}/reservations")
async def get_board_games_reservations(id: PydanticObjectId, _: BOARD_GAMES_ADMIN_AUTH) -> list[ReservationOut]:
    reservations = await board_games_repo.read_board_games_reservations(id)
    if reservations is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board game not found")
    return [ReservationOut.from_document(r) for r in reservations]


@router.get("/admin/reservations")
async def get_reservations(
    _: BOARD_GAMES_ADMIN_AUTH, how: str = Query("current", pattern="^(current|all)$")
) -> list[ReservationOut]:
    if how == "current":
        reservations = await board_games_repo.read_current_reservations()
    else:  # how == "all"
        reservations = await board_games_repo.read_reservations()
    return [ReservationOut.from_document(r) for r in reservations]


@router.patch("/admin/reservations/{id}")
async def edit_reservation(
    id: PydanticObjectId,
    body: board_games_repo.UpdateReservationAdmin,
    _: BOARD_GAMES_ADMIN_AUTH,
) -> ReservationOut:
    reservation = await board_games_repo.update_reservation_admin(id, body.status, body.borrower_name, body.return_date)
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    return ReservationOut.from_document(reservation)


@router.delete("/admin/reservations/{id}")
async def remove_reservation(id: PydanticObjectId, _: BOARD_GAMES_ADMIN_AUTH) -> None:
    deleted = await board_games_repo.delete_reservation_admin(id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")


# --------------------------------------------------------------------------- #
# Board games — public
# --------------------------------------------------------------------------- #


@router.get("/board-games")
async def get_all_board_games(_: INH_TOKEN_AUTH) -> list[BoardGameWithAvailabilityOut]:
    return await board_games_repo.read_all_with_availability()


@router.get("/board-games/{id}/photo", response_class=RedirectResponse)
async def get_board_game_photo(id: PydanticObjectId) -> RedirectResponse:
    board_game = await board_games_repo.read(id)
    if board_game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board game not found")
    if not board_game.photo_file_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No photo available")
    return RedirectResponse(url=photos_repo.get_url(board_game.photo_file_id, THUMBNAIL_SIZE))


# --------------------------------------------------------------------------- #
# Reservations — user
# --------------------------------------------------------------------------- #


@router.get("/users/me/reservations")
async def get_users_reservations(
    current_user: INH_TOKEN_AUTH, how: str = Query("current", pattern="^(current|all)$")
) -> list[ReservationOut]:
    if how == "current":
        reservations = await board_games_repo.read_user_current_reservations(current_user.innohassle_id)
    else:  # how == "all"
        reservations = await board_games_repo.read_user_reservations(current_user.innohassle_id)
    return [ReservationOut.from_document(r) for r in reservations]


@router.post("/board-games/{id}/reservations")
async def make_reservation(
    id: PydanticObjectId,
    current_user: INH_TOKEN_AUTH,
    body: board_games_repo.CreateReservation,
) -> ReservationOut:
    try:
        reservation = await board_games_repo.create_reservation_for_game(
            id,
            current_user.innohassle_id,
            current_user.email,
            body,
        )
    except board_games_repo.BoardGameNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board game not found") from exc
    except board_games_repo.ReservationConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ReservationOut.from_document(reservation)


@router.patch("/users/me/reservations/{id}")
async def edit_user_reservation(
    id: PydanticObjectId,
    body: board_games_repo.UpdateReservation,
    current_user: INH_TOKEN_AUTH,
) -> ReservationOut:
    try:
        reservation = await board_games_repo.update_user_reservation(id, current_user.innohassle_id, body)
    except board_games_repo.ReservationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found") from exc
    except board_games_repo.ReservationConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ReservationOut.from_document(reservation)


@router.delete("/users/me/reservations/{id}")
async def remove_user_reservation(
    id: PydanticObjectId,
    current_user: INH_TOKEN_AUTH,
) -> None:
    try:
        await board_games_repo.delete_user_reservation(id, current_user.innohassle_id)
    except board_games_repo.ReservationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found") from exc
    except board_games_repo.ReservationConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
