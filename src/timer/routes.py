from fastapi import APIRouter, Request, status
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.dependencies import INH_TOKEN_AUTH
from src.timer import repository
from src.timer.schemas import CreateTimer, ViewTimer

router = APIRouter(tags=["Timer"], route_class=AutoDeriveResponsesAPIRoute)


@router.get("/hello")
async def hello(auth: INH_TOKEN_AUTH) -> dict[str, str]:
    return {"message": f"hello, {auth.email}"}


@router.post("/timers", status_code=status.HTTP_201_CREATED)
async def create_timer(body: CreateTimer, auth: INH_TOKEN_AUTH, request: Request) -> ViewTimer:
    """Create a timer with optional checkpoints and grant its creator update/delete permissions."""
    return await repository.create_timer(request.app.state.sql_storage, body, auth.innohassle_id)
