"""
Clubs list and management.
"""

from typing import cast

import beanie.exceptions
import filetype
import pyvips
from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from pymongo.errors import DuplicateKeyError
from starlette import status
from starlette.responses import RedirectResponse

from src.clubs.dependencies import CLUBS_ADMIN_AUTH
from src.clubs.mongo import Club
from src.inh_accounts_sdk import inh_accounts

from . import clubs_repo
from .logos_repo import logos_repo

router = APIRouter(
    prefix="/clubs",
    tags=["Clubs"],
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.get("/", responses={status.HTTP_200_OK: {"description": "List of clubs"}})
async def get_clubs_list() -> list[Club]:
    """Get list of clubs."""
    return await clubs_repo.read_all()


@router.post(
    "/",
    responses={
        status.HTTP_201_CREATED: {"description": "New club is created"},
        status.HTTP_403_FORBIDDEN: {"description": "Only admin can create the club"},
    },
)
async def create_club(club_info: clubs_repo.CreateClub, _: CLUBS_ADMIN_AUTH) -> Club:
    """Create a new club."""
    return await clubs_repo.create(club_info)


@router.get(
    "/by-id/{id}",
    responses={
        status.HTTP_200_OK: {"description": "Club info"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def get_club_info(id: PydanticObjectId) -> Club:
    """Get club info."""
    club = await clubs_repo.read(id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    return club


@router.get(
    "/by-slug/{slug}",
    responses={
        status.HTTP_200_OK: {"description": "Club info"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def get_club_info_by_slug(slug: str) -> Club:
    """Get club info."""
    club = await clubs_repo.read_by_slug(slug)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    return club


@router.post(
    "/by-id/{id}",
    responses={
        status.HTTP_200_OK: {"description": "Changed club info successfully"},
        status.HTTP_403_FORBIDDEN: {"description": "Only admin can change club info"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def edit_club_info(id: PydanticObjectId, club_info: clubs_repo.UpdateClub, _: CLUBS_ADMIN_AUTH) -> Club:
    """Edit a club info."""
    # TODO: Allow club leaders to edit some info
    if club_info.new_leader_email:
        new_leader_data = await inh_accounts.get_user(email=club_info.new_leader_email)
        if not new_leader_data:
            raise HTTPException(status_code=404, detail="New leader email not found")
        club_info.leader_innohassle_id = new_leader_data.id
        club_info.new_leader_email = None

    club = await clubs_repo.update(id, club_info.to_club_schema())
    if club is None:
        raise HTTPException(status_code=404, detail="Club not found")
    return club


@router.post(
    "/by-slug/{slug}",
    responses={
        status.HTTP_200_OK: {"description": "Changed club info successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Slug already exists"},
        status.HTTP_403_FORBIDDEN: {"description": "Only admin can change club info"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def edit_club_info_by_slug(slug: str, update_club: clubs_repo.UpdateClub, _: CLUBS_ADMIN_AUTH) -> Club:
    """Edit a club info."""
    # TODO: Allow club leaders to edit some info
    if update_club.new_leader_email:
        new_leader_data = await inh_accounts.get_user(email=update_club.new_leader_email)
        if not new_leader_data:
            raise HTTPException(status_code=404, detail="New leader email not found")
        update_club.leader_innohassle_id = new_leader_data.id
        update_club.new_leader_email = None

    club = await clubs_repo.read_by_slug(slug)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    try:
        updated_club = await clubs_repo.update(club.id, update_club.to_club_schema())
        if updated_club is None:  # pragma: no cover
            raise HTTPException(status_code=400, detail="Failed to update club info")  # pragma: no cover
        return updated_club
    except beanie.exceptions.RevisionIdWasChanged, DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Slug already exists")


@router.delete(
    "/by-id/{id}",
    responses={
        status.HTTP_200_OK: {"description": "Deleted club successfully"},
        status.HTTP_403_FORBIDDEN: {"description": "Only admin can delete the club"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def delete_club(id: PydanticObjectId, _: CLUBS_ADMIN_AUTH) -> None:
    """Delete a club."""
    result = await clubs_repo.delete(id)
    if not result:
        raise HTTPException(status_code=404, detail="Club not found")


@router.get(
    "/by-id/{id}/logo",
    responses={
        status.HTTP_307_TEMPORARY_REDIRECT: {"description": "Redirect to the club logo"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found or no logo available"},
    },
    response_class=RedirectResponse,
)
async def get_club_logo(id: PydanticObjectId) -> RedirectResponse:
    """Get club info."""
    club = await clubs_repo.read(id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    if not club.logo_file_id:
        raise HTTPException(status_code=404, detail="No logo available")

    return RedirectResponse(url=logos_repo.get_club_logo_url(club.logo_file_id, 512))


@router.post(
    "/by-id/{id}/logo",
    responses={
        status.HTTP_200_OK: {"description": "Changed club logo successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid content type"},
        status.HTTP_403_FORBIDDEN: {"description": "Only admin can change club logo"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def set_club_logo(id: PydanticObjectId, logo_file: UploadFile, _: CLUBS_ADMIN_AUTH) -> Club:
    """Set a club logo picture."""
    # TODO: Allow club leaders to change logo
    club = await clubs_repo.read(id)
    if club is None:
        raise HTTPException(status_code=404, detail="Club not found")

    bytes_ = await logo_file.read()
    content_type = logo_file.content_type
    if content_type is None:  # pragma: no cover
        kind = filetype.guess(bytes_)
        content_type = kind.mime if kind else None

    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail=f"Invalid content type ({content_type})")

    # Convert to webp and resize to 512
    image = cast(pyvips.Image, pyvips.Image.new_from_buffer(bytes_, ""))
    image_bytes = cast(bytes, image.write_to_buffer(".webp"))
    image_512 = cast(pyvips.Image, pyvips.Image.thumbnail_buffer(bytes_, 512, height=512))
    image_512_bytes = cast(bytes, image_512.write_to_buffer(".webp[Q=95,min-size]"))

    # Save file
    logo_file_id = str(PydanticObjectId())
    logos_repo.put_club_logo(logo_file_id, None, image_bytes, "image/webp")
    logos_repo.put_club_logo(logo_file_id, 512, image_512_bytes, "image/webp")

    club.logo_file_id = logo_file_id
    await club.save()
    return club
