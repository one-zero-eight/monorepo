from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.dependencies import INH_TOKEN_AUTH
from src.timer import repository
from src.timer.schemas import CreateTimer, UpdateTimer, ViewInvitation, ViewTimer

router = APIRouter(tags=["Timer"], route_class=AutoDeriveResponsesAPIRoute)


@router.get("/hello")
async def hello(auth: INH_TOKEN_AUTH) -> dict[str, str]:
    return {"message": f"hello, {auth.email}"}


@router.post("/timers", status_code=status.HTTP_201_CREATED)
async def create_timer(body: CreateTimer, auth: INH_TOKEN_AUTH, request: Request) -> ViewTimer:
    """Create a timer with optional checkpoints and grant its creator update/delete/invite permissions."""
    return await repository.create_timer(request.app.state.sql_storage, body, auth.innohassle_id)


@router.get("/timers")
async def list_timers(auth: INH_TOKEN_AUTH, request: Request) -> list[ViewTimer]:
    """List timers created or joined by the current user, newest first."""
    return await repository.list_timers(request.app.state.sql_storage, auth.innohassle_id)


@router.get("/timers/{timer_id}")
async def get_timer(timer_id: int, auth: INH_TOKEN_AUTH, request: Request) -> ViewTimer:
    """Get a timer with its checkpoints and participants. Requires membership, regardless of permissions."""
    try:
        return await repository.get_timer(request.app.state.sql_storage, timer_id, auth.innohassle_id)
    except repository.TimerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer not found") from exc


@router.put("/timers/{timer_id}")
async def update_timer(
    timer_id: int,
    body: UpdateTimer,
    auth: INH_TOKEN_AUTH,
    request: Request,
) -> ViewTimer:
    """Replace the timer's title, time interval and complete checkpoint list. Requires update permission."""
    try:
        return await repository.update_timer(request.app.state.sql_storage, timer_id, auth.innohassle_id, body)
    except (repository.TimerNotFoundError, repository.TimerUpdateForbiddenError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer not found") from exc


@router.delete("/timers/{timer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timer(timer_id: int, auth: INH_TOKEN_AUTH, request: Request) -> Response:
    """Delete a timer and its participant records. Requires delete permission."""
    try:
        await repository.delete_timer(request.app.state.sql_storage, timer_id, auth.innohassle_id)
    except (repository.TimerNotFoundError, repository.TimerDeleteForbiddenError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/timers/{timer_id}/invitations", status_code=status.HTTP_201_CREATED)
async def create_invitation(timer_id: int, auth: INH_TOKEN_AUTH, request: Request) -> ViewInvitation:
    """Generate and store a new UUID4 invitation. Only the creator with invite permission can do this."""
    try:
        return await repository.create_invitation(request.app.state.sql_storage, timer_id, auth.innohassle_id)
    except (repository.TimerNotFoundError, repository.TimerInviteForbiddenError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timer not found") from exc


@router.post("/invitations/{invitation_uuid}/join")
async def join_timer(invitation_uuid: UUID, auth: INH_TOKEN_AUTH, request: Request) -> ViewTimer:
    """Join through a reusable invitation. Existing membership and permissions remain unchanged."""
    try:
        return await repository.join_timer(request.app.state.sql_storage, invitation_uuid, auth.innohassle_id)
    except repository.InvitationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found") from exc
