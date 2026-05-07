from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from starlette import status

import src.modules.clubs.crud as clubs_crud
import src.modules.leaders.crud as c
from src.api import docs

router = APIRouter(
    prefix="/leaders",
    tags=["Leaders"],
    route_class=AutoDeriveResponsesAPIRoute,
)
_description = """
Leaders info.
"""
docs.TAGS_INFO.append({"description": _description, "name": str(router.tags[0])})


@router.get(
    "/",
    responses={
        status.HTTP_200_OK: {"description": "Info about all club leaders"},
    },
)
async def get_all_leaders() -> dict[str, c.Leader | None]:
    """Get all club leaders."""
    clubs = await clubs_crud.read_all()
    return await c.read_many_by_innohassle_ids([club.leader_innohassle_id for club in clubs])


@router.get(
    "/by-club-id/{id}",
    responses={
        status.HTTP_200_OK: {"description": "Club leader info"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def get_club_leader_by_id(id: PydanticObjectId) -> c.Leader | None:
    """Get club leader info."""
    club = await clubs_crud.read(id)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    return await c.read_by_innohassle_id(club.leader_innohassle_id)


@router.get(
    "/by-club-slug/{slug}",
    responses={
        status.HTTP_200_OK: {"description": "Club leader info"},
        status.HTTP_404_NOT_FOUND: {"description": "Club not found"},
    },
)
async def get_club_leader_by_slug(slug: str) -> c.Leader | None:
    """Get club leader info."""
    club = await clubs_crud.read_by_slug(slug)
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    return await c.read_by_innohassle_id(club.leader_innohassle_id)
