"""
Lists of scenes for maps.
"""

__all__ = ["router"]

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.logging_ import logger

from . import maps_repo
from .config import settings
from .pdf_generator import generate_all_maps_pdf
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


@router.get("/pdf")
def export_pdf() -> FileResponse:
    pdf_path = settings.static_directory / "all_maps.pdf"
    if not pdf_path.exists():
        generate_all_maps_pdf()
    return FileResponse(pdf_path, filename="maps.pdf", media_type="application/pdf")
