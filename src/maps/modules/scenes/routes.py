"""
Lists of bookings for rooms.
"""

__all__ = ["router"]

from fastapi import APIRouter, Query

from src.api.logging_ import logger
from src.config_schema import Scene
from src.modules.scenes.repository import scene_repository
from src.modules.scenes.schemas import SearchResult

router = APIRouter(tags=["Scenes"])


@router.get("/scenes/")
def scenes() -> list[Scene]:
    return scene_repository.get_all()


@router.get("/scenes/areas/search")
def search_areas(query: str = Query(..., min_length=1)) -> list[SearchResult]:
    result = scene_repository.search(query=query)
    logger.info(f"Searching areas for `{query}`, Results: {result}")
    return result
