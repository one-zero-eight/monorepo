"""
Clubs list and management.
"""

from io import BytesIO

import beanie.exceptions
import filetype
from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from PIL import Image
from pymongo.errors import DuplicateKeyError
from starlette import status
from starlette.responses import RedirectResponse

from src.clubs.dependencies import CLUB_LEADER_OR_ADMIN, CLUBS_ADMIN_AUTH
from src.clubs.modules.users import users_repo
from src.clubs.mongo import Club, PendingClubUpdate, UserRole
from src.common_pydantic import BaseSchema
from src.dependencies import INH_TOKEN_AUTH, OPTIONAL_INH_TOKEN_AUTH
from src.inh_accounts_sdk import inh_accounts

from . import clubs_repo
from .description_images_repo import description_images_repo
from .logos_repo import logos_repo

router = APIRouter(
    prefix="/clubs",
    tags=["Clubs"],
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.get("/", responses={status.HTTP_200_OK: {"description": "List of clubs"}})
async def get_clubs_list(auth: OPTIONAL_INH_TOKEN_AUTH) -> list[Club]:
    """Get list of clubs."""
    clubs = await clubs_repo.read_all()
    
    is_admin = False
    if auth:
        clubs_user = await users_repo.read_by_innohassle_id(auth.innohassle_id)
        is_admin = clubs_user and clubs_user.role == UserRole.ADMIN

    for club in clubs:
        if not is_admin and (not auth or club.leader_innohassle_id != auth.innohassle_id):
            club.pending_update = None
            
    return clubs


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
async def get_club_info(id: PydanticObjectId, auth: OPTIONAL_INH_TOKEN_AUTH) -> Club:
    """Get club info."""
    club = await clubs_repo.read(id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
        
    is_admin = False
    if auth:
        clubs_user = await users_repo.read_by_innohassle_id(auth.innohassle_id)
        is_admin = clubs_user and clubs_user.role == UserRole.ADMIN
        
    if not is_admin and (not auth or club.leader_innohassle_id != auth.innohassle_id):
        club.pending_update = None
        
    return club


@router.get(
    "/by-slug/{slug}",
    responses={
        status.HTTP_200_OK: {"description": "Club info"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def get_club_info_by_slug(slug: str, auth: OPTIONAL_INH_TOKEN_AUTH) -> Club:
    """Get club info."""
    club = await clubs_repo.read_by_slug(slug)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
        
    is_admin = False
    if auth:
        clubs_user = await users_repo.read_by_innohassle_id(auth.innohassle_id)
        is_admin = clubs_user and clubs_user.role == UserRole.ADMIN
        
    if not is_admin and (not auth or club.leader_innohassle_id != auth.innohassle_id):
        club.pending_update = None
        
    return club


@router.post(
    "/by-id/{id}",
    responses={
        status.HTTP_200_OK: {"description": "Changed club info successfully"},
        status.HTTP_403_FORBIDDEN: {"description": "Only admin or leader can change club info"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def edit_club_info(id: PydanticObjectId, club_info: clubs_repo.UpdateClub, auth: INH_TOKEN_AUTH) -> Club:
    """Edit a club info."""
    club = await clubs_repo.read(id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
        
    clubs_user = await users_repo.read_by_innohassle_id(auth.innohassle_id)
    is_admin = clubs_user and clubs_user.role == UserRole.ADMIN
    is_leader = club.leader_innohassle_id == auth.innohassle_id
    
    if not is_admin and not is_leader:
        raise HTTPException(status_code=403, detail="Only admin or leader can change club info")

    if club_info.new_leader_email:
        new_leader_data = await inh_accounts.get_user(email=club_info.new_leader_email)
        if not new_leader_data:
            raise HTTPException(status_code=404, detail="New leader email not found")
        club_info.leader_innohassle_id = new_leader_data.id
        club_info.new_leader_email = None

    if is_admin:
        updated_club = await clubs_repo.update(id, club_info.to_club_schema())
        if updated_club is None:
            raise HTTPException(status_code=404, detail="Club not found")
        return updated_club
    else:
        club.pending_update = PendingClubUpdate(**club_info.model_dump(exclude={'new_leader_email', 'pending_update'}))
        await club.save()
        return club


@router.post(
    "/by-slug/{slug}",
    responses={
        status.HTTP_200_OK: {"description": "Changed club info successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Slug already exists"},
        status.HTTP_403_FORBIDDEN: {"description": "Only admin or leader can change club info"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def edit_club_info_by_slug(slug: str, update_club: clubs_repo.UpdateClub, auth: INH_TOKEN_AUTH) -> Club:
    """Edit a club info."""
    club = await clubs_repo.read_by_slug(slug)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
        
    clubs_user = await users_repo.read_by_innohassle_id(auth.innohassle_id)
    is_admin = clubs_user and clubs_user.role == UserRole.ADMIN
    is_leader = club.leader_innohassle_id == auth.innohassle_id
    
    if not is_admin and not is_leader:
        raise HTTPException(status_code=403, detail="Only admin or leader can change club info")

    if update_club.new_leader_email:
        new_leader_data = await inh_accounts.get_user(email=update_club.new_leader_email)
        if not new_leader_data:
            raise HTTPException(status_code=404, detail="New leader email not found")
        update_club.leader_innohassle_id = new_leader_data.id
        update_club.new_leader_email = None

    if is_admin:
        try:
            updated_club = await clubs_repo.update(club.id, update_club.to_club_schema())
            if updated_club is None:  # pragma: no cover
                raise HTTPException(status_code=400, detail="Failed to update club info")  # pragma: no cover
            return updated_club
        except beanie.exceptions.RevisionIdWasChanged:
            raise HTTPException(status_code=400, detail="Slug already exists")
        except DuplicateKeyError:
            raise HTTPException(status_code=400, detail="Slug already exists")
    else:
        club.pending_update = PendingClubUpdate(**update_club.model_dump(exclude={'new_leader_email', 'pending_update'}))
        await club.save()
        return club


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
        status.HTTP_403_FORBIDDEN: {"description": "Only admin or leader can change club logo"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def set_club_logo(id: PydanticObjectId, logo_file: UploadFile, auth: INH_TOKEN_AUTH) -> Club:
    """Set a club logo picture."""
    club = await clubs_repo.read(id)
    if club is None:
        raise HTTPException(status_code=404, detail="Club not found")

    clubs_user = await users_repo.read_by_innohassle_id(auth.innohassle_id)
    is_admin = clubs_user and clubs_user.role == UserRole.ADMIN
    is_leader = club.leader_innohassle_id == auth.innohassle_id
    
    if not is_admin and not is_leader:
        raise HTTPException(status_code=403, detail="Only admin or leader can change club logo")

    bytes_ = await logo_file.read()
    content_type = logo_file.content_type
    if content_type is None:  # pragma: no cover
        kind = filetype.guess(bytes_)
        content_type = kind.mime if kind else None

    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail=f"Invalid content type ({content_type})")

    # Convert to webp and resize to 512
    image = Image.open(BytesIO(bytes_))

    full_buf = BytesIO()
    image.save(full_buf, format="WEBP")
    image_bytes = full_buf.getvalue()

    thumb = image.copy()
    thumb.thumbnail((512, 512), Image.Resampling.LANCZOS)
    thumb_buf = BytesIO()
    thumb.save(thumb_buf, format="WEBP", quality=95, method=6)
    image_512_bytes = thumb_buf.getvalue()

    # Save file
    logo_file_id = str(PydanticObjectId())
    logos_repo.put_club_logo(logo_file_id, None, image_bytes, "image/webp")
    logos_repo.put_club_logo(logo_file_id, 512, image_512_bytes, "image/webp")

    if is_admin:
        club.logo_file_id = logo_file_id
    else:
        if not club.pending_update:
            club.pending_update = PendingClubUpdate(**club.model_dump(exclude={'pending_update'}))
        club.pending_update.logo_file_id = logo_file_id

    await club.save()
    return club


class DescriptionImageUploadResponse(BaseSchema):
    image_id: str
    "File ID to reference in club description"


@router.get(
    "/description-images/{image_id}",
    responses={
        status.HTTP_307_TEMPORARY_REDIRECT: {"description": "Redirect to the description image"},
        status.HTTP_404_NOT_FOUND: {"description": "Image not found"},
    },
    response_class=RedirectResponse,
)
async def get_description_image(image_id: str) -> RedirectResponse:
    """Get a club description image."""
    if not description_images_repo.exists(image_id):
        raise HTTPException(status_code=404, detail="Image not found")

    return RedirectResponse(url=description_images_repo.get_url(image_id))


@router.post(
    "/by-id/{id}/description-images",
    responses={
        status.HTTP_200_OK: {"description": "Description image uploaded successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid content type"},
        status.HTTP_403_FORBIDDEN: {"description": "Only club leader or admin can upload description images"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def upload_description_image(
    _: CLUB_LEADER_OR_ADMIN,
    image_file: UploadFile,
) -> DescriptionImageUploadResponse:
    """Upload an image for use in club description."""
    bytes_ = await image_file.read()
    content_type = image_file.content_type
    if content_type is None:  # pragma: no cover
        kind = filetype.guess(bytes_)
        content_type = kind.mime if kind else None

    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail=f"Invalid content type ({content_type})")

    image = Image.open(BytesIO(bytes_))
    buf = BytesIO()
    image.save(buf, format="WEBP", quality=90)
    image_bytes = buf.getvalue()

    image_id = str(PydanticObjectId())
    description_images_repo.put(image_id, image_bytes, "image/webp")

    return DescriptionImageUploadResponse(image_id=image_id)


@router.get(
    "/pending-updates",
    responses={
        status.HTTP_200_OK: {"description": "List of clubs with pending updates"},
        status.HTTP_403_FORBIDDEN: {"description": "Only admin can view all pending updates"},
    },
)
async def get_pending_updates(_: CLUBS_ADMIN_AUTH) -> list[Club]:
    """Get list of clubs with pending updates."""
    return await clubs_repo.get_pending_updates()


@router.post(
    "/by-id/{id}/approve-update",
    responses={
        status.HTTP_200_OK: {"description": "Approved pending update"},
        status.HTTP_403_FORBIDDEN: {"description": "Only admin can approve updates"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def approve_club_update(id: PydanticObjectId, _: CLUBS_ADMIN_AUTH) -> Club:
    """Approve a pending club update."""
    club = await clubs_repo.approve_update(id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    return club


@router.post(
    "/by-id/{id}/reject-update",
    responses={
        status.HTTP_200_OK: {"description": "Rejected pending update"},
        status.HTTP_403_FORBIDDEN: {"description": "Only admin can reject updates"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def reject_club_update(id: PydanticObjectId, _: CLUBS_ADMIN_AUTH) -> Club:
    """Reject a pending club update."""
    club = await clubs_repo.reject_update(id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    return club
