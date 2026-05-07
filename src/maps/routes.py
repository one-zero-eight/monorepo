"""
Lists of scenes for maps.
"""

__all__ = ["router"]

from fastapi import APIRouter, Query
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.logging_ import logger

from .repository import scene_repository
from .schemas import Scene, SearchResult

router = APIRouter(tags=["Scenes"], route_class=AutoDeriveResponsesAPIRoute)


@router.get("/scenes/")
def scenes() -> list[Scene]:
    return scene_repository.get_all()


@router.get("/scenes/areas/search")
def search_areas(query: str = Query(..., min_length=1)) -> list[SearchResult]:
    result = scene_repository.search(query=query)
    logger.info(f"Searching areas for `{query}`, Results: {result}")
    return result
