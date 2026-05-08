"""
Club leader information.
"""

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from starlette import status

from src.clubs.modules.clubs import clubs_repo
from src.clubs.modules.leaders import leaders_repo

router = APIRouter(
    prefix="/leaders",
    tags=["Leaders"],
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.get(
    "/",
    responses={
        status.HTTP_200_OK: {"description": "Info about all club leaders"},
    },
)
async def get_all_leaders() -> dict[str, leaders_repo.Leader | None]:
    """Get all club leaders."""
    clubs = await clubs_repo.read_all()
    return await leaders_repo.read_many_by_innohassle_ids(
        [club.leader_innohassle_id for club in clubs if club.leader_innohassle_id]
    )


@router.get(
    "/by-club-id/{id}",
    responses={
        status.HTTP_200_OK: {"description": "Club leader info"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def get_club_leader_by_id(id: PydanticObjectId) -> leaders_repo.Leader | None:
    """Get club leader info."""
    club = await clubs_repo.read(id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    if club.leader_innohassle_id is None:
        return None

    return await leaders_repo.read_by_innohassle_id(club.leader_innohassle_id)


@router.get(
    "/by-club-slug/{slug}",
    responses={
        status.HTTP_200_OK: {"description": "Club leader info"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def get_club_leader_by_slug(slug: str) -> leaders_repo.Leader | None:
    """Get club leader info."""
    club = await clubs_repo.read_by_slug(slug)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    if club.leader_innohassle_id is None:
        return None

    return await leaders_repo.read_by_innohassle_id(club.leader_innohassle_id)
