"""
Operational endpoints for the When2Meet service.
"""

from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

router = APIRouter(tags=["When2Meet"], route_class=AutoDeriveResponsesAPIRoute)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
