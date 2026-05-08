"""
Lists of scenes for maps.
"""

__all__ = ["router"]

from fastapi import APIRouter, Query
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.logging_ import logger

from . import maps_repo
from .schemas import Scene, SearchResult

router = APIRouter(tags=["Scenes"], route_class=AutoDeriveResponsesAPIRoute)


@router.get("/scenes/")
def scenes() -> list[Scene]:
    return maps_repo.get_all_scenes()


@router.get("/scenes/areas/search")
def search_areas(query: str = Query(..., min_length=1)) -> list[SearchResult]:
    result = maps_repo.search_areas(query=query)
    logger.info(f"Searching areas for `{query}`, Results: {result}")
    return result
