from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.events.config import settings

router = APIRouter(
    tags=["Locales"],
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.get("/locales")
async def get_locales() -> list[str]:
    """Get the allowed locales list."""
    return settings.locales
